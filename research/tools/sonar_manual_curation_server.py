"""Local-only human sonar/camera curation service with append-only revisions.

Source files are read-only. Raw pixel edge xyxy is the annotation coordinate.
All production data is allowlisted by the resolved native development manifest.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict, defaultdict
import copy
import csv
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, quote, urlparse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
from check_official_sonar_coordinates import Geometry, beam_count, load_beam_tables

DEFAULT_OUT = ROOT / 'DataSet/sonar_manual_curation'
STATES = {'geometry_retained', 'manual_revised', 'unresolved', 'excluded'}
ACCEPTED = {'geometry_retained', 'manual_revised'}
CATEGORY_MODEL = {'100lbs_aircraft_bomb': '100lbs', 'incindiary_grenade': 'incindiary', 'mortar_shell': 'mortar_shell'}
FLOOR_RECORDING = '2023-09-21_160551'
FLOOR_CANDIDATE_ID = 'floor_target_pca_fixed'
TARGET_FRAME = {'100lbs_aircraft_bomb': 'target/100lbs', 'incindiary_grenade': 'target/incendiary', 'mortar_shell': 'target/mortar_shell'}
PAPER_TARGET = dict(classes=3, recordings_per_class=10, frames_per_recording=100, total=3000)


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def target_frame_for(row):
    """Only the explicitly identified floor recording uses the floor target."""
    if row['recording'] == FLOOR_RECORDING:
        if row['category'] != '100lbs_aircraft_bomb':
            raise APIError(409, 'Floor recording category differs from the registered mapping')
        return 'target/100lbs_floor'
    return TARGET_FRAME[row['category']]


def inside(path, root):
    path = Path(path).resolve()
    try:
        path.relative_to(Path(root).resolve())
    except ValueError:
        raise APIError(422, 'Path is outside the allowed source directory')
    return path


def valid_bbox(box, width, height, required=False):
    if box is None:
        if required:
            raise APIError(422, 'A valid bounding box is required')
        return None
    if not isinstance(box, list) or len(box) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box):
        raise APIError(422, 'Bounding box must contain four finite numbers')
    x0, y0, x1, y1 = map(float, box)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise APIError(422, f'Bounding box must lie inside {width} x {height}')
    return [x0, y0, x1, y1]


def projection_bbox(uv, width, height, padding=0.):
    if not len(uv):
        return None
    lo = np.maximum(uv.min(0)-padding, [0., 0.])
    hi = np.minimum(uv.max(0)+padding, [float(width), float(height)])
    return None if np.any(hi <= lo) else np.r_[lo, hi].tolist()


class DatasetSource:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.manifest_path = self.root / 'DataSet/camera_temporal_all/manifest-resolved.json'
        self.camera_root = self.manifest_path.parent.resolve()
        raw_manifest = self.manifest_path.read_bytes()
        self.manifest_hash = sha_bytes(raw_manifest)
        manifest = json.loads(raw_manifest)
        self.dataset_id = 'uxo-native-sd-' + self.manifest_hash[:16]
        self.manifest_provenance = dict(path=str(self.manifest_path), sha256=self.manifest_hash,
                                        scope=manifest['scope'], native_membership='resolved manifest native identities, including unpaired_role=null')
        self.rows = {}; self.recordings = defaultdict(list); self.sd_paths = {}; self.label_paths = {}; self.rec_dirs = {}
        admitted = {r['recording'] for r in manifest['recordings']}
        if admitted != set(manifest['identity']['recordings']) or len(admitted) != 40:
            raise RuntimeError('Manifest must identify exactly the existing 40 approved development recordings')
        for row in manifest['items']:
            sid = row['sample']; rec = row['recording']; index = int(row['aris_frame'])
            if rec not in admitted or row.get('paired_role') not in (None, 'train', 'val', 'val_id'):
                raise RuntimeError('Illegal recording/role in allowed manifest')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}_\d{6}', rec) or sid != f'{rec}_{index:04d}' or row['category'] not in CATEGORY_MODEL:
                raise RuntimeError('Unexpected sample identity/category')
            if sid in self.rows:
                raise RuntimeError('Duplicate sample identity')
            source_image = Path(row['original_image']).resolve()
            recdir = source_image.parent.parent
            if source_image.parent.name != 'gopro' or recdir.name != rec or source_image.stem != f'{index:04d}':
                raise RuntimeError('Original image identity/path mismatch')
            if rec in self.rec_dirs and self.rec_dirs[rec] != recdir:
                raise RuntimeError('Recording has conflicting source directories')
            self.rec_dirs[rec] = recdir
            self.rows[sid] = row; self.recordings[rec].append(sid)
            self.sd_paths[sid] = inside(self.camera_root / row['reference_sd'], self.camera_root) if row.get('reference_sd') else None
            self.label_paths[sid] = inside(self.camera_root / row['label_copy'], self.camera_root) if row.get('label_copy') else None
        self.suggested = set(); self.sd_available = {}
        for rec, members in self.recordings.items():
            members.sort(key=lambda s: self.rows[s]['aris_frame'])
            # All frames remain selectable; this queue never changes review state.
            positions = np.linspace(0, len(members)-1, min(100, len(members))).round().astype(int)
            self.suggested.update(members[i] for i in positions)
            for sid in members:
                p = self.sd_paths[sid]
                self.sd_available[sid] = bool(p and p.is_file())
        self.lock = threading.RLock()
        self.loaded = OrderedDict(); self.metadata = {}; self.models = {}; self.fixed_sources = {}
        mst = self.manifest_path.stat()
        self.hash_cache = {str(self.manifest_path): ((mst.st_size, mst.st_mtime_ns), self.manifest_hash)}
        self.image_cache = OrderedDict()
        self.tables = load_beam_tables()
        self.frame_cache_limit = 24
        self.calibration_path = self.root / 'DataSet/sonar_model_registration_consistency/calibration-versions.json'
        self.old_models_path = self.root / 'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
        self.mortar_path = self.root / 'DataSet/mortar_fixed_registration/freeze-model.json'

    def require(self, sample):
        if not isinstance(sample, str) or sample not in self.rows:
            raise APIError(404, 'Unknown or unauthorized sample')
        return self.rows[sample]

    def source_bytes(self, path):
        path = Path(path)
        if not path.is_file():
            raise APIError(404, 'Required source file is missing')
        st = path.stat(); sig = (st.st_size, st.st_mtime_ns)
        key = str(path)
        if key in self.hash_cache and self.hash_cache[key][0] != sig:
            raise APIError(409, 'Source changed during this session; stop and audit before continuing')
        data = path.read_bytes(); digest = sha_bytes(data)
        if key in self.hash_cache and self.hash_cache[key][1] != digest:
            raise APIError(409, 'Source content changed during this session')
        self.hash_cache[key] = (sig, digest)
        return data, dict(path=key, sha256=digest, bytes=len(data))

    def validate_provenance(self, provenance, full_hash=False):
        """Refuse stale cached frames; saves also hash every contributing source."""
        if isinstance(provenance, dict):
            if isinstance(provenance.get('path'), str) and provenance.get('sha256'):
                path = Path(provenance['path'])
                try:
                    st = path.stat()
                except OSError:
                    raise APIError(409, 'A displayed source is now missing; reload after auditing it')
                cached = self.hash_cache.get(str(path))
                if cached and cached[0] != (st.st_size, st.st_mtime_ns):
                    raise APIError(409, 'A displayed source changed; stop and audit before saving')
                if full_hash and self.source_bytes(path)[1]['sha256'] != provenance['sha256']:
                    raise APIError(409, 'Displayed source hash no longer matches')
            for value in provenance.values():
                self.validate_provenance(value, full_hash)
        elif isinstance(provenance, list):
            for value in provenance:
                self.validate_provenance(value, full_hash)

    def validate_for_save(self, frame):
        with self.lock:
            self.validate_provenance(frame['provenance'], full_hash=True)

    def recording_metadata(self, rec):
        if rec not in self.metadata:
            directory = self.rec_dirs[rec]
            mbytes, mp = self.source_bytes(directory/'aris_frame_meta.csv')
            gbytes, gp = self.source_bytes(directory/'gantry.csv')
            wanted = {int(self.rows[s]['aris_frame']) for s in self.recordings[rec]}
            metadata = {int(r['FrameIndex']): r for r in csv.DictReader(io.StringIO(mbytes.decode('utf-8-sig'))) if int(r['FrameIndex']) in wanted}
            gantry = {int(r['aris_frame_idx']): r for r in csv.DictReader(io.StringIO(gbytes.decode('utf-8-sig'))) if int(r['aris_frame_idx']) in wanted}
            self.metadata[rec] = metadata, gantry, mp, gp
        return self.metadata[rec]

    def ensure_model(self, model_name):
        if not self.fixed_sources:
            calb, calp = self.source_bytes(self.calibration_path)
            oldb, oldp = self.source_bytes(self.old_models_path)
            mortb, mortp = self.source_bytes(self.mortar_path)
            self.calibration_version = json.loads(calb)['versions']['release_current']
            self.statics = {k: np.asarray(v) for k, v in self.calibration_version['parent_from_child_matrices'].items()}
            self.old_model_info = json.loads(oldb)['models']; self.mortar_info = json.loads(mortb)
            self.fixed_sources = dict(calibration=calp, old_pca=oldp, mortar_fixed=mortp)
        if model_name not in self.models:
            info = self.old_model_info[model_name]
            objb, objp = self.source_bytes(info['source'])
            if objp['sha256'] != info['source_sha256']:
                raise APIError(409, 'OBJ source differs from the frozen model')
            vertices, faces = [], []
            for line in objb.decode('utf-8').splitlines():
                parts = line.split()
                if not parts: continue
                if parts[0] == 'v': vertices.append(list(map(float, parts[1:4])))
                elif parts[0] == 'f':
                    ids = [int(x.split('/')[0]) for x in parts[1:]]
                    ids = [i-1 if i>0 else len(vertices)+i for i in ids]
                    faces.extend([[ids[0], ids[i], ids[i+1]] for i in range(1,len(ids)-1)])
            v = np.asarray(vertices); tri = v[np.asarray(faces)]
            rawdense = np.concatenate([v, tri.mean(1), (tri[:,0]+tri[:,1])/2, (tri[:,1]+tri[:,2])/2, (tri[:,2]+tri[:,0])/2])
            sim = np.asarray(info['mesh_to_target_similarity']); world = np.asarray(info['world_from_target'])@sim
            variants = [dict(id='old_pca_fixed', label='旧固定 PCA 候选（未验证，待人工检查）', transform=world,
                             source='sonar_fixed_mesh: frozen PCA s/R/t, fixed negative beam convention; regenerated on official coordinate API',
                             source_hash=self.fixed_sources['old_pca']['sha256'], padding=1., validation='not_training_gt')]
            if model_name == 'mortar_shell':
                best = next(c for c in self.mortar_info['candidates'] if c['id']==self.mortar_info['best_display_candidate_id'])
                variants.append(dict(id='mortar_fixed_start00', label='mortar 固定拟合 start-00（跨录音未全局验证）',
                                     transform=np.asarray(best['world_from_obj_similarity']),source='mortar_fixed_registration: frozen start-00, fixed .580m scale',
                                     source_hash=self.fixed_sources['mortar_fixed']['sha256'],padding=0.,validation='unstable_candidates; unvalidated outside original two recordings'))
            self.models[model_name] = rawdense, variants, objp
        return self.models[model_name]

    def floor_variant(self, row, original):
        """Correct the known target identity; do not refit the frozen PCA mesh."""
        if target_frame_for(row) != 'target/100lbs_floor':
            raise APIError(409, 'Floor target correction requested for an unauthorized recording')
        directory = self.rec_dirs[row['recording']]
        if directory.parent.name != '100lbs_bomb_(floor)':
            raise APIError(409, 'Floor recording source directory no longer matches its target')
        notes_bytes, notes_source = self.source_bytes(directory/'notes.txt')
        notes = notes_bytes.decode('utf-8-sig').splitlines()
        matches = [(i+1, line) for i, line in enumerate(notes) if line.strip() == '- target: 100lbs_bomb (floor)']
        if len(matches) != 1:
            raise APIError(409, 'Floor target notes evidence is absent or ambiguous')
        _, yaml_source = self.source_bytes(self.calibration_version['source'])
        if yaml_source['sha256'] != self.calibration_version['sha256']:
            raise APIError(409, 'Official calibration YAML differs from the audited matrix source')
        world_target = self.statics['target/100lbs_floor']
        mesh_target = np.asarray(self.old_model_info['100lbs']['mesh_to_target_similarity'])
        evidence = dict(recording=row['recording'], source_directory=str(directory),
                        notes=notes_source|dict(line=matches[0][0], text=matches[0][1]),
                        official_yaml=yaml_source, calibration_matrices=self.fixed_sources['calibration'],
                        frozen_mesh_registration=self.fixed_sources['old_pca'])
        return original | dict(
            id=FLOOR_CANDIDATE_ID, label='floor target 修正 + 旧 PCA（注册仍未验证）',
            transform=world_target@mesh_target,
            source='160551 only: official target/100lbs_floor replaces normal target/100lbs; frozen PCA mesh registration unchanged',
            source_hash=self.fixed_sources['calibration']['sha256'], validation='target_mapping_corrected_only; mesh_registration_not_validated',
            target_frame='target/100lbs_floor', world_from_target=world_target.tolist(),
            mesh_to_target_similarity=mesh_target.tolist(), target_mapping_evidence=evidence,
            supersedes_candidate_id='old_pca_fixed', correction_id='floor_target_mapping_20261112',
            source_hashes=dict(calibration_matrices=self.fixed_sources['calibration']['sha256'],
                               official_yaml=yaml_source['sha256'], frozen_mesh_registration=self.fixed_sources['old_pca']['sha256'],
                               recording_notes=notes_source['sha256']))

    def candidates(self, row, metadata, gantry, geom):
        points, variants, objp = self.ensure_model(CATEGORY_MODEL[row['category']])
        target_frame = target_frame_for(row)
        if target_frame == 'target/100lbs_floor':
            variants = [self.floor_variant(row, variants[0])]
        wa = np.eye(4)
        wa[:3,:3] = self.statics['setup/ar3'][:3,:3] @ Rotation.from_euler('xyz',[float(metadata[k]) for k in ('SonarRoll','SonarTilt','SonarPan')],degrees=True).as_matrix()
        wa[:3,3] = np.array([float(gantry[k]) for k in 'xyz']) + self.statics['setup/ar3'][:3,3]
        world_sonar = wa @ self.statics['setup/aris'] @ self.statics['setup/sonar']
        inv = np.linalg.inv(world_sonar)
        result=[]
        for variant in variants:
            sonar_model = inv @ variant['transform']
            p = points @ sonar_model[:3,:3].T + sonar_model[:3,3]
            ranges=np.linalg.norm(p,axis=1); beta=-np.degrees(np.arctan2(p[:,0],p[:,2])); elevation=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
            valid=(p[:,2]>0)&(ranges>=geom.r0)&(ranges<=geom.data_range)&(beta>=geom.beams[0,1])&(beta<=geom.beams[-1,2])&(np.abs(elevation)<=7)
            uv=geom.points_to_raw_edges(ranges[valid],beta[valid])
            polar=geom.points_to_polar_index(ranges[valid],beta[valid])+.5
            candidate = {k: variant[k] for k in ('id','label','source','source_hash','validation')} | dict(
                bbox_xyxy=projection_bbox(uv,geom.w,geom.h,variant['padding']),
                polar_bbox_xyxy=projection_bbox(polar,geom.W,geom.H,0.),
                raw_padding_beam_bin=variant['padding'], polar_padding_px=0.,elevation_limit_deg=7.,
                coordinates='raw native pixel edges xyxy; polar contextual pixel edges',sampled_surface_points=len(points),visible_sample_count=int(valid.sum()))
            if variant['id'] == FLOOR_CANDIDATE_ID:
                candidate.update({k: variant[k] for k in ('target_frame','world_from_target','mesh_to_target_similarity',
                    'target_mapping_evidence','supersedes_candidate_id','correction_id','source_hashes')})
            result.append(candidate)
        provenance = dict(model=objp,calibration=self.fixed_sources['calibration'],frozen_source_files=self.fixed_sources,world_from_sonar=world_sonar.tolist(),
                            beam_convention='-atan2(sonar_x,sonar_z), fixed diagnostic convention, not rescanned',
                            candidate_status='unvalidated suggestions; missing candidate does not prohibit manual drawing')
        if target_frame == 'target/100lbs_floor':
            provenance['target_mapping_evidence'] = variants[0]['target_mapping_evidence']
            provenance['target_frame'] = target_frame
        return result, provenance

    def frame(self, sample):
        row=self.require(sample)
        with self.lock:
            if sample in self.loaded:
                self.validate_provenance(self.loaded[sample]['provenance'])
                self.loaded.move_to_end(sample)
                return copy.deepcopy(self.loaded[sample])
            index=int(row['aris_frame']);rec=row['recording'];directory=self.rec_dirs[rec]
            rawb, rawp=self.source_bytes(directory/'aris_raw'/f'{index:04d}.pgm')
            raw=cv2.imdecode(np.frombuffer(rawb,np.uint8),cv2.IMREAD_GRAYSCALE)
            if raw is None: raise APIError(422,'Raw sonar could not be decoded')
            height,width=raw.shape
            metas,gantries,mp,gp=self.recording_metadata(rec)
            if index not in metas or index not in gantries: raise APIError(422,'Requested identity lacks metadata/gantry')
            m=metas[index];g=gantries[index]
            if int(m['FrameTime'])!=int(row['aris_time_us']): raise APIError(409,'ARIS timestamp differs from manifest')
            geom=Geometry(m,self.tables[beam_count(m['PingMode'])],1000.)
            if (height,width)!=(geom.h,geom.w): raise APIError(422,'Raw dimensions differ from metadata')
            camera_path=self.sd_paths[sample];camera_prov=None;available=False
            if camera_path and camera_path.is_file():
                camb,camera_prov=self.source_bytes(camera_path)
                cam=cv2.imdecode(np.frombuffer(camb,np.uint8),cv2.IMREAD_COLOR)
                if cam is None or cam.shape[:2]!=(360,640): raise APIError(422,'SD reference is not a valid 640 x 360 image')
                available=True
            label_path=self.label_paths[sample];label_prov=None;original_box=None
            if label_path and label_path.is_file():
                lb,label_prov=self.source_bytes(label_path);label=json.loads(lb)
                if label.get('class')!=row['category']: raise APIError(422,'Camera label category differs from manifest')
                original_box=[float(label[k]) for k in ('x_min','y_min','x_max','y_max')]
                if any(not math.isfinite(x) for x in original_box): raise APIError(422,'Non-finite original camera box')
            warnings=[]
            if not available: warnings.append('SD reference unavailable; this frame cannot be accepted as a pair')
            if original_box is None: warnings.append('Original SD box unavailable; draw and document a camera box before paired acceptance')
            try:
                candidate_list,candidate_prov=self.candidates(row,m,g,geom)
            except (APIError,ValueError,KeyError) as exc:
                if isinstance(exc,APIError) and exc.status==409: raise
                candidate_list=[];candidate_prov={};warnings.append('Candidate unavailable: '+str(exc))
            url=lambda kind:'/api/image?sample='+quote(sample)+'&kind='+kind
            value=dict(sample=sample,recording=rec,category=row['category'],aris_frame=index,suggested=sample in self.suggested,
                       sonar=dict(width=width,height=height,url=url('sonar'),polar_url=url('polar'),polar_width=geom.W,polar_height=geom.H,candidates=candidate_list),
                       camera=dict(width=640,height=360,url=url('camera') if available else None,bbox_xyxy=original_box,available=available,
                                   label_source='original SD-coordinate label_copy, unscaled' if original_box is not None else None,
                                   label_available=original_box is not None,original_bbox_xyxy=original_box),
                       review=None,warnings=warnings,
                       provenance=dict(dataset_id=self.dataset_id,manifest=self.manifest_provenance,raw=rawp,camera_sd=camera_prov,camera_label=label_prov,
                                       metadata=mp,gantry=gp,candidates=candidate_prov,aris_time_us=row['aris_time_us'],
                                       original_image_path_not_used=row['original_image'],original_label_path=row['original_label'],
                                       historical_paired_role=row.get('paired_role'),image_coordinates='native raw edge xyxy and SD 640x360 edge xyxy'))
            self.validate_provenance(value['provenance'])
            self.loaded[sample]=value
            while len(self.loaded)>self.frame_cache_limit: self.loaded.popitem(last=False)
            return copy.deepcopy(value)

    def image(self,sample,kind):
        row=self.require(sample)
        if kind not in ('sonar','polar','camera'): raise APIError(404,'Unknown image kind')
        with self.lock:
            frame=self.frame(sample)
            if kind=='camera':
                if not frame['camera']['available']: raise APIError(404,'SD reference missing')
                data,prov=self.source_bytes(self.sd_paths[sample])
                return data,'image/jpeg',prov['sha256']
            rawb,prov=self.source_bytes(Path(frame['provenance']['raw']['path']))
            key=(sample,kind,prov['sha256'])
            if key in self.image_cache:
                self.image_cache.move_to_end(key)
                return self.image_cache[key]
            raw=cv2.imdecode(np.frombuffer(rawb,np.uint8),cv2.IMREAD_GRAYSCALE)
            if kind=='polar':
                m=self.recording_metadata(row['recording'])[0][int(row['aris_frame'])]
                raw=Geometry(m,self.tables[beam_count(m['PingMode'])],1000.).render(raw)
            ok,encoded=cv2.imencode('.png',raw,[cv2.IMWRITE_PNG_COMPRESSION,3])
            if not ok: raise APIError(500,'Image encoding failed')
            result=(encoded.tobytes(),'image/png',sha_bytes(encoded.tobytes()))
            self.image_cache[key]=result
            while len(self.image_cache)>36: self.image_cache.popitem(last=False)
            return result


class ReviewStore:
    def __init__(self,out,dataset_id,test_mode=False):
        self.out=Path(out).resolve()
        if test_mode and self.out==DEFAULT_OUT.resolve(): raise RuntimeError('Test writes require isolated output')
        self.out.mkdir(parents=True,exist_ok=True)
        self.dataset_id=dataset_id;self.test_mode=test_mode
        self.journal=self.out/'reviews.jsonl';self.snapshot=self.out/'reviews-latest.json'
        self.lock=threading.RLock();self.latest={};self.events=[]
        self._file_lock=open(self.out/'reviews.lock','a+b')
        self._file_lock.seek(0,2)
        if self._file_lock.tell()==0: self._file_lock.write(b'0');self._file_lock.flush()
        self._file_lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self._file_lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._file_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self._file_lock.close()
            raise RuntimeError('Another curation service is already using this output directory')
        try: self.replay()
        except Exception:
            self.close()
            raise

    def close(self):
        if not self._file_lock.closed: self._file_lock.close()

    def replay(self):
        if self.journal.exists():
            data=self.journal.read_bytes()
            if data and not data.endswith(b'\n'):
                raise RuntimeError('Review journal has an incomplete last line; preserve and audit before writing')
            for number,line in enumerate(data.splitlines(),1):
                event=json.loads(line)
                if event.get('dataset_id')!=self.dataset_id or bool(event.get('test_mode'))!=bool(self.test_mode):
                    raise RuntimeError('Review journal dataset/test mode mismatch')
                sample=event['sample'];expected=self.latest.get(sample,{}).get('revision',0)+1
                if event['review']['revision']!=expected: raise RuntimeError(f'Journal revision discontinuity at line {number}')
                self.latest[sample]=event['review'];self.events.append(event)
        if self.events:
            try: self.write_snapshot()
            except OSError as exc: print('Journal restored; snapshot unavailable:', str(exc), flush=True)

    def write_snapshot(self):
        temporary=self.out/'reviews-latest.json.tmp'
        with open(temporary,'wb') as stream:
            stream.write(json_bytes(dict(dataset_id=self.dataset_id,event_count=len(self.events),reviews=self.latest)))
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.snapshot)

    def get(self,sample):
        with self.lock: return copy.deepcopy(self.latest.get(sample))

    def commit(self,sample,expected,review,provenance):
        with self.lock:
            previous=self.latest.get(sample)
            revision=0 if previous is None else previous['revision']
            if expected!=revision: raise APIError(409,f'Revision conflict: expected {expected}, current {revision}; reload before saving')
            result=copy.deepcopy(review)|dict(revision=revision+1,saved_at=utc_now(),reviewer_type='automation_test' if self.test_mode else 'human')
            event=dict(schema_version=1,dataset_id=self.dataset_id,test_mode=self.test_mode,event_id=len(self.events)+1,
                       sample=sample,previous_revision=revision,previous_review=previous,review=result,provenance=provenance)
            with open(self.journal,'ab') as stream:
                stream.write(json_bytes(event)+b'\n');stream.flush();os.fsync(stream.fileno())
            self.latest[sample]=result;self.events.append(event)
            warning=None
            try:
                self.write_snapshot()
            except OSError as exc:
                # Journal is authoritative and already durable. Do not report a
                # failed save that would invite an accidental duplicate action.
                warning='Journal committed; latest snapshot will be rebuilt on reload: '+str(exc)
            return copy.deepcopy(result),warning


class CurationApp:
    def __init__(self,source,out,test_mode=False,static_root=DEFAULT_OUT):
        self.source=source;self.out=Path(out).resolve();self.test_mode=test_mode
        self.static_root=Path(static_root).resolve()
        self.store=ReviewStore(self.out,source.dataset_id,test_mode)
        self.request_lock=threading.RLock()

    def counts(self,members):
        result=dict(reviewed=0,accepted=0,manual_revised=0,unresolved=0,excluded=0,geometry_retained=0)
        for sid in members:
            review=self.store.get(sid)
            if review:
                result['reviewed']+=1;result[review['state']]+=1
                result['accepted']+=int(review.get('accepted',False))
        return result

    def catalog(self):
        recordings=[]
        for rec,members in sorted(self.source.recordings.items()):
            recordings.append(dict(recording=rec,category=self.source.rows[members[0]]['category'],total=len(members),
                                   sd_available=sum(self.source.sd_available[s] for s in members),
                                   suggested_count=sum(s in self.source.suggested for s in members),target=100,
                                   **self.counts(members)))
        return dict(dataset_id=self.source.dataset_id,manifest=self.source.manifest_provenance,recordings=recordings,
                    paper_target=PAPER_TARGET,review_count=sum(x['reviewed'] for x in recordings),
                    accepted_count=sum(x['accepted'] for x in recordings),native_count=len(self.source.rows),
                    test_mode=self.test_mode,local_target_per_recording=100,
                    selection_note='Uniform 100-frame queue is a suggestion only; all manifest-native frames remain selectable')

    def recording(self,rec):
        if rec not in self.source.recordings: raise APIError(404,'Unknown or unauthorized recording')
        frames=[]
        for sid in self.source.recordings[rec]:
            review=self.store.get(sid)
            frames.append(dict(sample=sid,aris_frame=self.source.rows[sid]['aris_frame'],suggested=sid in self.source.suggested,
                               state=None if review is None else review['state'],accepted=bool(review and review.get('accepted')),
                               sd_available=self.source.sd_available[sid],revision=0 if review is None else review['revision']))
        return dict(recording=rec,category=self.source.rows[frames[0]['sample']]['category'],frames=frames,target=100,**self.counts([f['sample'] for f in frames]))

    def frame(self,sid):
        frame=self.source.frame(sid);frame['review']=self.store.get(sid)
        return frame

    def review(self,payload):
        if not isinstance(payload,dict): raise APIError(422,'Review body must be an object')
        with self.request_lock:
            sample=payload.get('sample');frame=self.source.frame(sample)
            expected=payload.get('expected_revision')
            if isinstance(expected,bool) or not isinstance(expected,int) or expected<0: raise APIError(422,'expected_revision must be a nonnegative integer')
            current=self.store.get(sample)
            if expected!=(current or {}).get('revision',0): raise APIError(409,'Revision conflict; reload the frame')
            state=payload.get('state');visibility=payload.get('visibility')
            if not isinstance(state,str) or state not in STATES: raise APIError(422,'Unknown review state')
            if visibility not in ('yes','no','uncertain'): raise APIError(422,'visibility must be yes, no, or uncertain')
            if not isinstance(payload.get('camera_ok'),bool): raise APIError(422,'camera_ok must be boolean')
            reviewer=payload.get('reviewer');reason=payload.get('reason','')
            if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>120: raise APIError(422,'Reviewer name or code is required')
            if not isinstance(reason,str) or len(reason)>4000: raise APIError(422,'Reason must be text under 4000 characters')
            candidate_id=payload.get('candidate_id')
            candidate=None
            if candidate_id is not None:
                candidate=next((c for c in frame['sonar']['candidates'] if c['id']==candidate_id),None)
                if candidate is None: raise APIError(422,'Unknown candidate_id for this sample')
            accepted=state in ACCEPTED
            sonar_box=valid_bbox(payload.get('sonar_bbox_xyxy'),frame['sonar']['width'],frame['sonar']['height'],accepted)
            camera_box=valid_bbox(payload.get('camera_bbox_xyxy'),640,360,accepted)
            if accepted and (visibility!='yes' or not frame['camera']['available'] or not payload['camera_ok']):
                raise APIError(422,'Accepted paired frames require visible=yes, SD image, camera_ok=true, and valid boxes')
            if state=='geometry_retained' and (candidate is None or candidate['bbox_xyxy'] is None or sonar_box!=candidate['bbox_xyxy']):
                raise APIError(422,'geometry_retained requires exact equality to the selected candidate box')
            camera_changed=camera_box!=frame['camera']['bbox_xyxy']
            sonar_changed=bool(sonar_box is not None and (candidate is None or sonar_box!=candidate['bbox_xyxy']))
            if (state in ('manual_revised','unresolved','excluded') or camera_changed or sonar_changed) and not reason.strip():
                raise APIError(422,'A reason is required for manual edits, unresolved, or excluded states')
            data=dict(state=state,accepted=accepted,sonar_bbox_xyxy=sonar_box,camera_bbox_xyxy=camera_box,
                      candidate_id=candidate_id,visibility=visibility,camera_ok=payload['camera_ok'],reason=reason.strip(),reviewer=reviewer.strip(),
                      camera_manually_changed=camera_changed,sonar_manually_changed=sonar_changed,
                      original_camera_bbox_xyxy=frame['camera']['bbox_xyxy'],selected_candidate=copy.deepcopy(candidate),
                      original_candidate_bbox_xyxy=None if candidate is None else candidate['bbox_xyxy'])
            prov=copy.deepcopy(frame['provenance'])|dict(source_candidates=frame['sonar']['candidates'],
                    image_dimensions=dict(sonar=[frame['sonar']['width'],frame['sonar']['height']],camera=[640,360]))
            self.source.validate_for_save(frame)
            saved,warning=self.store.commit(sample,expected,data,prov)
            return dict(ok=True,sample=sample,review=saved,warning=warning,counts=self.counts(self.source.recordings[frame['recording']]))

    def export(self):
        with self.store.lock:
            grouped=defaultdict(list)
            for event in self.store.events: grouped[event['sample']].append(copy.deepcopy(event))
            items=[]
            for sid,history in sorted(grouped.items()):
                row=self.source.require(sid);latest=history[-1]
                items.append(dict(sample=sid,recording=row['recording'],category=row['category'],aris_frame=row['aris_frame'],
                                  review=copy.deepcopy(latest['review']),provenance=copy.deepcopy(latest['provenance']),event_history=history))
            return dict(schema_version=1,dataset_id=self.source.dataset_id,manifest=self.source.manifest_provenance,
                        exported_at=utc_now(),test_mode=self.test_mode,annotation_coordinates='native raw sonar pixel-edge xyxy; SD camera 640x360 pixel-edge xyxy',
                        paper_target=PAPER_TARGET,coverage=self.catalog()['recordings'],accepted_count=sum(i['review']['accepted'] for i in items),
                        reviewed_count=len(items),event_count=len(self.store.events),items=items,
                        note='Human curation candidate pool; no training split or final protocol is established by export')


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version='SonarCuration/1.0'
        def log_message(self,fmt,*args):
            if self.path.startswith('/api/') and not self.path.startswith('/api/image'):
                print(self.log_date_time_string(),fmt%args,flush=True)

        def send_data(self,status,body,content_type='application/json; charset=utf-8',headers=None):
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            for key,value in (headers or {}).items(): self.send_header(key,value)
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError): pass

        def send_json(self,status,value): self.send_data(status,json_bytes(value))

        def local_request(self,write=False):
            allowed_host=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host','')!=allowed_host: raise APIError(403,'Requests must use the local service address')
            if write:
                origin=self.headers.get('Origin')
                if origin and origin!=f'http://{allowed_host}':
                    raise APIError(403,'Cross-origin writes are not allowed')
                if self.headers.get('Sec-Fetch-Site')=='cross-site': raise APIError(403,'Cross-site writes are not allowed')

        def do_GET(self):
            try:
                self.local_request();url=urlparse(self.path);query=parse_qs(url.query)
                single=lambda key:query.get(key,[''])[0]
                if url.path=='/api/catalog': return self.send_json(200,app.catalog())
                if url.path=='/api/recording': return self.send_json(200,app.recording(single('id')))
                if url.path=='/api/frame': return self.send_json(200,app.frame(single('id')))
                if url.path=='/api/export':
                    return self.send_data(200,json_bytes(app.export()),headers={'Content-Disposition':'attachment; filename="sonar-curation-export.json"'})
                if url.path=='/api/image':
                    data,ctype,digest=app.source.image(single('sample'),single('kind'))
                    return self.send_data(200,data,ctype,{'ETag':'"'+digest+'"'})
                static={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if url.path not in static: raise APIError(404,'Not found')
                path=app.static_root/static[url.path]
                if not path.is_file(): raise APIError(404,'Frontend not yet installed')
                content_type={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[path.name]
                return self.send_data(200,path.read_bytes(),content_type)
            except APIError as exc: self.send_json(exc.status,dict(error=str(exc)))
            except Exception as exc:
                print('GET error:',repr(exc),flush=True);self.send_json(500,dict(error=str(exc)))

        def do_POST(self):
            try:
                self.local_request(write=True)
                if urlparse(self.path).path!='/api/review': raise APIError(404,'Not found')
                if self.headers.get('Content-Type','').lower().split(';')[0].strip()!='application/json': raise APIError(415,'application/json required')
                try: size=int(self.headers.get('Content-Length','0'))
                except ValueError: raise APIError(400,'Invalid content length')
                if size<=0 or size>65536: raise APIError(413,'Invalid or oversized review body')
                try: payload=json.loads(self.rfile.read(size))
                except (ValueError,UnicodeError): raise APIError(400,'Invalid JSON')
                return self.send_json(200,app.review(payload))
            except APIError as exc: self.send_json(exc.status,dict(error=str(exc)))
            except Exception as exc:
                print('POST error:',repr(exc),flush=True);self.send_json(500,dict(error=str(exc)))
    return Handler


def start_server(app,port=8765,allow_fallback=True):
    ports=[port] if not allow_fallback or port==0 else list(range(port,port+10))
    last=None
    for candidate in ports:
        try:
            server=ThreadingHTTPServer(('127.0.0.1',candidate),make_handler(app));server.daemon_threads=True
            return server
        except OSError as exc: last=exc
    raise last


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--test-mode',action='store_true',help='Mark events as automated testing; requires isolated --out')
    args=parser.parse_args()
    if args.test_mode and args.out.resolve()==DEFAULT_OUT.resolve(): parser.error('--test-mode requires an isolated --out')
    source=DatasetSource();app=CurationApp(source,args.out,args.test_mode)
    server=start_server(app,args.port)
    info=dict(url=f'http://127.0.0.1:{server.server_port}',pid=os.getpid(),dataset_id=source.dataset_id,
              output=str(args.out.resolve()),test_mode=args.test_mode,started_at=utc_now(),source_count=len(source.rows),recordings=len(source.recordings))
    (args.out/'server-info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close();app.store.close()


if __name__=='__main__': main()
