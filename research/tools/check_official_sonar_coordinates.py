"""Audit raw/polar2 pixel coordinates without a physical mesh or sonar-axis fit.

Public APIs use beam-table angles (negative at raw column 0), not physical
azimuth. Geometry.points_to_polar_index returns continuous pixel-index coords;
Geometry.points_to_raw_edges returns edge coords (a raw pixel center is i+.5).
The polygon renderer separately preserves the official quantization and draw
order. Merely importing this module performs no dataset reads or writes.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image, ImageDraw

UPSTREAM = ROOT / 'related_work/uxo-upstream-history/scripts'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_beam_tables():
    """Read only literal public beam arrays; execute no upstream module."""
    tree = ast.parse((UPSTREAM / 'common/aris_definitions.py').read_text(encoding='utf-8'))
    arrays = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('BeamWidthsAris3000_64', 'BeamWidthsAris3000_128'):
                    arrays[int(target.id.rsplit('_', 1)[1])] = np.array(ast.literal_eval(node.value), dtype=float)
    assert set(arrays) == {64, 128}
    return arrays


def beam_count(pingmode):
    if int(pingmode) in (6, 7, 8):
        return 64
    if int(pingmode) in (9, 10, 11, 12):
        return 128
    raise ValueError('This ARIS 3000 audit admits only the official 64/128 beam tables')


def linear_extrapolate(x, xp, fp):
    x = np.asarray(x, dtype=float)
    ix = np.clip(np.searchsorted(xp, x, side='right') - 1, 0, len(xp) - 2)
    return fp[ix] + (x - xp[ix]) * (fp[ix + 1] - fp[ix]) / (xp[ix + 1] - xp[ix])


@dataclass
class Geometry:
    metadata: dict
    beams: np.ndarray
    resolution: float = 1000.

    def __post_init__(self):
        self.h = int(self.metadata['SamplesPerBeam'])
        self.w = len(self.beams)
        assert self.w == beam_count(self.metadata['PingMode'])
        self.c = float(self.metadata['SoundSpeed'])
        self.delay = float(self.metadata['SampleStartDelay'])
        self.period = float(self.metadata['SamplePeriod'])
        self.r0 = self.delay * 1e-6 * self.c / 2
        self.dr = self.period * 1e-6 * self.c / 2
        # Preserve the source expression order, including the extra canvas bin.
        self.canvas_range = self.r0 + self.period * (self.h + 1) * 1e-6 * self.c / 2
        self.data_range = self.r0 + self.period * self.h * 1e-6 * self.c / 2
        half_angle = (self.beams[-1, 2] - self.beams[0, 1]) / 2
        self.H = int(np.ceil(self.canvas_range * self.resolution))
        self.W = int(np.ceil(self.canvas_range * np.tan(np.deg2rad(half_angle)) * 2 * self.resolution))
        assert np.max(np.abs(self.beams[:-1, 2] - self.beams[1:, 1])) < 1e-8
        # Every actual beam boundary is an integer column edge; retain the
        # published centers too, which need not be exact arithmetic midpoints.
        self.angle_knots = np.r_[np.column_stack([self.beams[:, 1], self.beams[:, 0]]).ravel(), self.beams[-1, 2]]
        self.column_knots = np.arange(2 * self.w + 1, dtype=float) / 2

    def points_to_raw_edges(self, ranges, beam_angles):
        """Fractional raw edge coords: sample center (col+.5,row+.5)."""
        u = linear_extrapolate(beam_angles, self.angle_knots, self.column_knots)
        v = (np.asarray(ranges) - self.r0) / self.dr
        return np.stack([u, v], axis=-1)

    def raw_edges_to_points(self, uv):
        uv = np.asarray(uv, dtype=float)
        a = linear_extrapolate(uv[..., 0], self.column_knots, self.angle_knots)
        r = self.r0 + uv[..., 1] * self.dr
        return r, a

    def points_to_polar_index(self, ranges, beam_angles):
        """Unrounded polar2 pixel-index coordinates after final horizontal flip."""
        r = np.asarray(ranges, dtype=float)
        a = np.deg2rad(np.asarray(beam_angles, dtype=float))
        return np.stack([self.W / 2 - 1 - r * np.sin(a) * self.resolution,
                         self.H - r * np.cos(a) * self.resolution], axis=-1)

    def polar_index_to_points(self, uv):
        uv = np.asarray(uv, dtype=float)
        x = (self.W / 2 - 1 - uv[..., 0]) / self.resolution
        z = (self.H - uv[..., 1]) / self.resolution
        return np.hypot(x, z), np.rad2deg(np.arctan2(x, z))

    def cell_polygons(self, after_flip=False):
        """Integer six-vertex polygons, [beam,bin,vertex,xy].

        This preserves the source trigonometry evaluation rather than replacing
        cos(90-beta) with sin(beta) before floor/ceil. Every cell, including zero
        intensity cells, must be drawn in ascending beam then bin order.
        """
        b = np.arange(self.h, dtype=float)
        lo = self.r0 + self.period * b * 1e-6 * self.c / 2
        hi = self.r0 + self.period * (b + 1) * 1e-6 * self.c / 2
        beta = self.beams[:, [1, 0, 2, 2, 0, 1]]
        radii = np.stack([hi, hi, hi, lo, lo, lo], axis=-1)
        theta = np.deg2rad(-beta + 90)
        x = radii[None, :, :] * np.cos(theta)[:, None, :] * self.resolution + self.W / 2
        y = -radii[None, :, :] * np.sin(theta)[:, None, :] * self.resolution + self.H
        for k in (0, 5):
            x[:, :, k] = np.floor(x[:, :, k])
        for k in (1, 4):
            x[:, :, k] = np.round(x[:, :, k])
        for k in (2, 3):
            x[:, :, k] = np.ceil(x[:, :, k])
        y[:, :, :3] = np.ceil(y[:, :, :3])
        y[:, :, 3:] = np.floor(y[:, :, 3:])
        if after_flip:
            x = self.W - 1 - x
        return np.stack([x, y], axis=-1).astype(np.int32)

    def render(self, frame):
        frame = np.asarray(frame)
        assert frame.shape == (self.h, self.w)
        output = np.zeros((self.H, self.W), dtype=np.uint8)
        polygons = self.cell_polygons()
        for i in range(self.w):
            for j in range(self.h):
                cv2.fillPoly(output, [np.ascontiguousarray(polygons[i, j])], int(frame[j, i]))
        return cv2.flip(output, 1)

    def description(self):
        return dict(raw_shape_hw=[self.h, self.w], polar_shape_hw=[self.H, self.W],
                    resolution_px_per_m=self.resolution, range_start_m=self.r0,
                    sample_bin_m=self.dr, last_sample_end_m=self.data_range,
                    canvas_range_m=self.canvas_range, extra_canvas_bin=True,
                    beam_angle_endpoints_deg=[float(self.beams[0, 1]), float(self.beams[-1, 2])],
                    polar_continuous_index_formula='u=W/2-1-r*sin(beta)*res; v=H-r*cos(beta)*res',
                    raw_edge_formula='u=piecewise_linear(actual beam edges i and centers i+.5); v=(r-r0)/dr')


def official_reference(tables):
    """Compile only the named public function AST, excluding all top-level code."""
    source = UPSTREAM / 'prep_2_aris_to_polar.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'aris_frame_to_polar2']
    assert len(selected) == 1
    scope = dict(np=np, cv2=cv2, get_beamcount_from_pingmode=beam_count,
                 BeamWidthsAris3000_64=tables[64], BeamWidthsAris3000_128=tables[128])
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), scope)
    return scope['aris_frame_to_polar2']


class MetadataShim:
    """The source function only needs metadata.iloc[frame_idx]."""
    def __init__(self, row):
        self.row = row
        self.iloc = self

    def __getitem__(self, key):
        return self.row


def image_difference(a, b):
    if a.shape != b.shape:
        return dict(same_shape=False, shape_a=list(a.shape), shape_b=list(b.shape), exact_equal=False)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return dict(same_shape=True, exact_equal=bool(np.array_equal(a, b)),
                different_pixels=int(np.count_nonzero(delta)), max_abs_difference=int(delta.max()),
                mean_abs_difference=float(delta.mean()))


def read_gray(path):
    data = Path(path).read_bytes()
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if frame is None:
        raise ValueError(f'Could not decode {path}')
    return frame


def save_image(path, frame):
    Image.fromarray(frame).save(path)


def run():
    out = ROOT / 'DataSet/sonar_registration_methods/coordinates'
    plan = ROOT / 'experiment/sonar-registration-methods-plan.md'
    assert plan.exists(), 'Pre-registration required'
    if (out / 'results.json').exists():
        raise RuntimeError('Preserve this run; use an explicitly named revision')
    out.mkdir(parents=True, exist_ok=True)
    selection = ROOT / 'DataSet/sonar_independent_registration/selection.json'
    manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
    rows = json.loads(selection.read_text(encoding='utf-8'))['samples']
    assert len(rows) == 18
    allowed = {r['sample']: r for r in json.loads(manifest_path.read_text(encoding='utf-8'))['items']
               if r.get('paired_role') in ('train', 'val', 'val_id')}
    assert all(r['sample'] in allowed and r['aris_frame'] == allowed[r['sample']]['aris_frame'] for r in rows)
    paths = {plan, selection, manifest_path, Path(__file__), UPSTREAM / 'prep_2_aris_to_polar.py',
             UPSTREAM / 'common/aris_definitions.py', UPSTREAM / 'config.yaml', UPSTREAM / 'release_1_export.py'}
    paths.update(Path(r[k]) for r in rows for k in ('raw_sonar_source', 'meta_source'))
    # Exact identity paths only; no directory enumeration or other frames.
    polar_paths = {r['sample']: Path(r['raw_sonar_source']).parent.parent / 'aris_polar' / f"{r['aris_frame']:04d}.png" for r in rows}
    paths.update(p for p in polar_paths.values() if p.exists())
    before = {str(p): digest(p) for p in sorted(paths)}
    (out / 'inputs-before.json').write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding='utf-8')
    tables = load_beam_tables()
    reference = official_reference(tables)
    synthetic = []
    for count in (64, 128):
        meta = dict(PingMode=6 if count == 64 else 9, SamplesPerBeam=16,
                    SoundSpeed=1500., SampleStartDelay=160., SamplePeriod=40.)
        for resolution in (200., 1000.):
            geom = Geometry(meta, tables[count], resolution)
            pattern = ((np.arange(16)[:, None] * 17 + np.arange(count)[None, :] * 23) % 256).astype(np.uint8)
            for label, frame in [('pattern', pattern), ('single-leftmost-raw', np.zeros_like(pattern)),
                                 ('single-rightmost-raw', np.zeros_like(pattern))]:
                if label == 'single-leftmost-raw':
                    frame[8, 0] = 255
                elif label == 'single-rightmost-raw':
                    frame[8, -1] = 255
                actual = geom.render(frame)
                expected = reference(frame, 0, MetadataShim(meta), resolution)
                diff = image_difference(actual, expected)
                assert diff['exact_equal'], f'Synthetic raster mismatch: {count}/{resolution}/{label}: {diff}'
                yy, xx = np.nonzero(actual)
                name = f'synthetic-{count}-{int(resolution)}-{label}.png'
                save_image(out / name, actual)
                synthetic.append(dict(beams=count, resolution=resolution, case=label, **diff,
                                      nonzero_pixels=len(xx), nonzero_bbox_xyxy=None if not len(xx) else [int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1)], image=name))
    cases = []
    meta_cache = {}
    for row in rows:
        rec = row['recording']
        if rec not in meta_cache:
            with open(row['meta_source'], encoding='utf-8', newline='') as f:
                meta_cache[rec] = {int(m['FrameIndex']): m for m in csv.DictReader(f)}
        meta = meta_cache[rec][row['aris_frame']]
        assert int(meta['FrameTime']) == allowed[row['sample']]['aris_time_us']
        raw = read_gray(row['raw_sonar_source'])
        geom = Geometry(meta, tables[beam_count(meta['PingMode'])], 1000.)
        assert raw.shape == (geom.h, geom.w)
        rendered = geom.render(raw)
        expected = reference(raw, 0, MetadataShim({k: float(v) if k in ('SoundSpeed', 'SampleStartDelay', 'SamplePeriod') else int(v) if k in ('PingMode', 'SamplesPerBeam') else v for k,v in meta.items()}), 1000.)
        diff = image_difference(rendered, expected)
        assert diff['exact_equal'], f'Actual raw raster mismatch {row["sample"]}: {diff}'
        filename = row['sample'] + '-official-polar2.png'
        save_image(out / filename, rendered)
        p = polar_paths[row['sample']]
        published = image_difference(rendered, read_gray(p)) if p.exists() else dict(available=False, checked_exact_path=str(p))
        # Roundtrip all beam/bin centers: this checks coordinates, not calibration.
        uu, vv = np.meshgrid(np.arange(geom.w)+.5, np.arange(geom.h)+.5)
        uv = np.stack([uu, vv], axis=-1)
        ranges, angles = geom.raw_edges_to_points(uv)
        uv2 = geom.points_to_raw_edges(ranges, angles)
        polar = geom.points_to_polar_index(ranges, angles)
        rr, aa = geom.polar_index_to_points(polar)
        # Compare the old fan after its scale alone is multiplied by 5.
        old_resolution = 200.
        old_range = geom.r0 + geom.h * geom.dr
        old_h = math.ceil(old_range * old_resolution)
        old_w = math.ceil(2 * old_range * np.tan(np.deg2rad(max(abs(geom.beams[0,1]), abs(geom.beams[-1,2])))) * old_resolution)
        old_uv = np.stack([old_w/2-ranges*np.sin(np.deg2rad(angles))*200,
                           old_h-ranges*np.cos(np.deg2rad(angles))*200], axis=-1)
        offset = polar - old_uv * 5
        case = dict(sample=row['sample'], aris_frame=row['aris_frame'], source_raw=str(row['raw_sonar_source']),
                    metadata=geom.description(), reference_difference=diff,
                    published_polar_path=str(p) if p.exists() else None, published_polar_difference=published,
                    image=filename, raw_roundtrip_max_px=float(np.max(np.abs(uv2-uv))),
                    polar_roundtrip_max_range_m=float(np.max(np.abs(rr-ranges))),
                    polar_roundtrip_max_beam_deg=float(np.max(np.abs(aa-angles))),
                    prior_fan_shape_hw=[old_h,old_w],
                    official_minus_five_times_prior_fan_coordinate_px=dict(min=offset.reshape(-1,2).min(0).tolist(),max=offset.reshape(-1,2).max(0).tolist()),
                    note='Old fan uses a different canvas and resampler; this is a continuous-point coordinate offset, not pixel-image equivalence.')
        cases.append(case)
        print(row['sample'], 'reference exact', diff['exact_equal'], 'published', published, flush=True)
    assert all(digest(p) == h for p,h in before.items())
    results = dict(run='sonar_registration_methods_official_coordinates', status='software_coordinate_checks_complete_not_physical_axis_certification',
                   inputs_unchanged=True, sample_count=18, test_access=False, parameter_fits=0, mesh_projection_runs=0,
                   reference_loading='AST only: aris_frame_to_polar2, no upstream module top-level execution',
                   config_resolution_px_per_m=1000, source_default_function_resolution=1000, source_main_fallback_resolution=500,
                   published_polar_note='Release export copies pre-rendered polar files; current config alone does not prove historical release resolution.',
                   synthetic=synthetic, frames=cases,
                   limitations=['Input beta is a beam-table angle; no physical x-axis sign is inferred here.',
                                'Continuous raw subpixel interpolation is our explicit convention between each actual angular edge and center; official renderer paints whole angular cells.',
                                'Continuous point projection differs from integer polygon rasterization; shared edges are overwritten by later cells.',
                                'Agreement of renderers does not certify mesh registration, sensor calibration, pose, visibility, or annotations.'])
    (out / 'results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    html = ['<!doctype html><meta charset="utf-8"><title>Official sonar pixel mapping audit</title><style>body{font:16px system-ui;background:#17212b;color:white;max-width:1300px;margin:auto}img{max-width:95%;height:auto}a{color:#8bd0ff}article{margin:2em 0}</style><h1>官方 raw / polar2 坐标审计</h1><p>只验证软件坐标映射；没有认证物理 beam 符号、模型注册或标注。18 个既有开发身份，无新 GT。</p><p><a href="results.json">完整数值与访问记录</a></p>']
    for case in cases:
        html += [f'<article><h2>{case["sample"]}</h2><p>官方函数与独立实现逐像素一致。发布图比较：{case["published_polar_difference"]}</p><img src="{case["image"]}" loading="lazy"></article>']
    (out / 'index.html').write_text('\n'.join(html), encoding='utf-8')


if __name__ == '__main__':
    run()
