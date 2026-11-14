"""Persistence and local HTTP controls, using isolated synthetic review data only."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import sonar_manual_curation_server as service


class SyntheticSource:
    dataset_id = 'synthetic-curation-test-only'
    manifest_provenance = {'path': 'synthetic-fixture', 'sha256': 'synthetic-manifest'}

    def __init__(self):
        self.rows = {sid: dict(sample=sid, recording='fixture', category='mortar_shell', aris_frame=i)
                     for i, sid in enumerate(['valid', 'missing-sd', 'out-of-bounds-original'])}
        self.recordings = {'fixture': list(self.rows)}
        self.sd_available = {'valid': True, 'missing-sd': False, 'out-of-bounds-original': True}
        self.suggested = {'valid'}
        self.changed = False

    def require(self, sample):
        if sample not in self.rows:
            raise service.APIError(404, 'Unknown or unauthorized sample')
        return self.rows[sample]

    def frame(self, sample):
        row = self.require(sample)
        box = [-2., 5., 20., 30.] if sample == 'out-of-bounds-original' else [10., 20., 60., 70.]
        candidate = dict(id='old_pca_fixed', label='Synthetic fixture', bbox_xyxy=[2., 3., 20., 30.],
                         source='fixture', source_hash='candidate-hash', polar_bbox_xyxy=[1., 1., 3., 3.])
        return dict(**row, sonar=dict(width=96, height=441, candidates=[candidate]),
                    camera=dict(width=640, height=360, available=self.sd_available[sample], bbox_xyxy=box),
                    provenance=dict(raw={'path': 'synthetic-raw', 'sha256': 'raw-hash'},
                                    camera_label={'path': 'synthetic-label', 'sha256': 'label-hash'}))

    def validate_for_save(self, frame):
        if self.changed:
            raise service.APIError(409, 'Source changed')

    def image(self, sample, kind):
        self.require(sample)
        if kind not in ('sonar', 'polar', 'camera'):
            raise service.APIError(404, 'Unknown image kind')
        return b'synthetic-image', 'image/png', 'synthetic-hash'


def payload(**updates):
    value = dict(sample='valid', expected_revision=0, state='geometry_retained',
                 sonar_bbox_xyxy=[2, 3, 20, 30], camera_bbox_xyxy=[10, 20, 60, 70],
                 candidate_id='old_pca_fixed', visibility='yes', camera_ok=True, reason='', reviewer='automated-test')
    value.update(updates)
    return value


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sonar-curation-test-')
        self.directory = Path(self.temp.name)
        self.source = SyntheticSource()
        self.app = service.CurationApp(self.source, self.directory, test_mode=True)

    def tearDown(self):
        self.app.store.close()
        self.temp.cleanup()

    def assert_rejected(self, request, status=422):
        events = len(self.app.store.events)
        with self.assertRaises(service.APIError) as caught:
            self.app.review(request)
        self.assertEqual(caught.exception.status, status)
        self.assertEqual(len(self.app.store.events), events)

    def test_no_automatic_acceptance_and_exact_geometry(self):
        self.assertEqual(self.app.catalog()['accepted_count'], 0)
        self.assertEqual(self.app.catalog()['native_count'], 3)
        self.app.frame('valid')
        self.assertEqual(self.app.catalog()['review_count'], 0)
        self.assert_rejected(payload(sonar_bbox_xyxy=[2, 3, 20, 30.00001]))
        saved = self.app.review(payload())['review']
        self.assertTrue(saved['accepted'])
        self.assertEqual(saved['reviewer_type'], 'automation_test')
        self.assertEqual(self.app.catalog()['accepted_count'], 1)

    def test_pair_requirements(self):
        for updates in [dict(visibility='uncertain'), dict(visibility='no'), dict(camera_ok=False),
                        dict(camera_ok='yes'), dict(camera_bbox_xyxy=None), dict(sonar_bbox_xyxy=None),
                        dict(sample='missing-sd'), dict(reviewer=''), dict(expected_revision=True)]:
            with self.subTest(updates=updates): self.assert_rejected(payload(**updates))

    def test_box_validation(self):
        for box in [[-1, 3, 20, 30], [2, 3, 97, 30], [2, 30, 20, 3], [2, 3, 2, 30],
                    [float('nan'), 3, 20, 30], [2, 3, float('inf'), 30], [True, 3, 20, 30], [1, 2, 3]]:
            with self.subTest(box=box):
                self.assert_rejected(payload(state='manual_revised', reason='box correction', sonar_bbox_xyxy=box))
        self.assert_rejected(payload(sample='out-of-bounds-original', camera_bbox_xyxy=[-2, 5, 20, 30]))
        self.app.review(payload(sample='out-of-bounds-original', camera_bbox_xyxy=[0, 5, 20, 30], reason='fix SD edge'))
        self.assertTrue(self.app.store.get('out-of-bounds-original')['camera_manually_changed'])

    def test_reasons_manual_history_and_export(self):
        self.assert_rejected(payload(state='manual_revised'))
        self.assert_rejected(payload(camera_bbox_xyxy=[11, 20, 60, 70]))
        first = self.app.review(payload())['review']
        revised = payload(expected_revision=1, state='manual_revised', sonar_bbox_xyxy=[4, 5, 22, 32],
                          camera_bbox_xyxy=[11, 20, 60, 70], reason='visible body boundary')
        second = self.app.review(revised)['review']
        self.assertEqual(second['revision'], 2)
        self.assertTrue(second['sonar_manually_changed'])
        self.assertTrue(second['camera_manually_changed'])
        self.assertEqual(second['original_candidate_bbox_xyxy'], [2., 3., 20., 30.])
        exported = self.app.export()
        self.assertEqual(exported['event_count'], 2)
        self.assertEqual(exported['accepted_count'], 1)
        self.assertEqual(exported['items'][0]['event_history'][1]['previous_review'], first)
        self.assertEqual(exported['items'][0]['provenance']['raw']['sha256'], 'raw-hash')
        self.assertEqual(exported['items'][0]['provenance']['source_candidates'][0]['source_hash'], 'candidate-hash')

    def test_unresolved_excluded_never_accepted(self):
        self.app.review(payload(state='unresolved', visibility='uncertain', sonar_bbox_xyxy=None,
                                camera_bbox_xyxy=None, candidate_id=None, camera_ok=False, reason='cannot identify target'))
        self.app.review(payload(sample='missing-sd', state='excluded', visibility='no', sonar_bbox_xyxy=None,
                                camera_bbox_xyxy=None, candidate_id=None, camera_ok=False, reason='SD absent'))
        self.assertEqual(self.app.catalog()['review_count'], 2)
        self.assertEqual(self.app.catalog()['accepted_count'], 0)

    def test_revision_conflict_and_source_change_do_not_mutate(self):
        self.app.review(payload())
        before = self.app.store.journal.read_bytes()
        self.assert_rejected(payload(), 409)
        self.source.changed = True
        self.assert_rejected(payload(expected_revision=1), 409)
        self.assertEqual(self.app.store.journal.read_bytes(), before)

    def test_restart_uses_journal_when_snapshot_fails(self):
        with patch.object(service.os, 'replace', side_effect=OSError('injected snapshot failure')):
            result = self.app.review(payload())
        self.assertIn('Journal committed', result['warning'])
        self.app.store.close()
        self.app = service.CurationApp(self.source, self.directory, test_mode=True)
        self.assertEqual(self.app.store.get('valid')['revision'], 1)
        self.assertEqual(self.app.catalog()['accepted_count'], 1)
        self.assertEqual(json.loads(self.app.store.snapshot.read_text())['event_count'], 1)
        self.app.review(payload(expected_revision=1, state='excluded', reason='new human review rejected frame'))
        self.assertEqual(self.app.catalog()['accepted_count'], 0)
        self.assertEqual(json.loads(self.app.store.snapshot.read_text())['event_count'], 2)

    def test_lock_mode_guard_and_partial_journal(self):
        with self.assertRaises(RuntimeError): service.ReviewStore(self.directory, self.source.dataset_id, True)
        with self.assertRaises(RuntimeError): service.ReviewStore(service.DEFAULT_OUT, self.source.dataset_id, True)
        self.app.review(payload())
        self.app.store.close()
        with self.assertRaises(RuntimeError): service.ReviewStore(self.directory, self.source.dataset_id, False)
        with self.assertRaises(RuntimeError): service.ReviewStore(self.directory, 'different-dataset', True)
        with open(self.directory/'reviews.jsonl', 'ab') as stream: stream.write(b'{"interrupted":')
        with self.assertRaises(RuntimeError): service.ReviewStore(self.directory, self.source.dataset_id, True)

    def test_unknown_identity(self):
        self.assert_rejected(payload(sample='../secret'), 404)
        self.assert_rejected(payload(candidate_id='unknown'))


class HTTPTests(unittest.TestCase):
    setUp = ReviewTests.setUp
    tearDown = ReviewTests.tearDown

    def test_http_api_local_origin_and_static_allowlist(self):
        (self.directory/'index.html').write_text('<title>Synthetic test</title>')
        (self.directory/'secret.json').write_text('not public')
        self.app.static_root = self.directory
        server = service.start_server(self.app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, data=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            body = None if data is None else json.dumps(data)
            hdr = {'Content-Type': 'application/json'} | (headers or {})
            connection.request(method, path, body=body, headers=hdr)
            response = connection.getresponse(); value = response.read(); status = response.status
            self.assertIsNone(response.getheader('Access-Control-Allow-Origin'))
            connection.close()
            return status, value
        try:
            self.assertEqual(request('GET', '/api/catalog')[0], 200)
            self.assertEqual(request('GET', '/')[0], 200)
            for path in ['/secret.json', '/../secret.json', '/api/image?sample=../secret&kind=sonar', '/api/frame?id=../secret']:
                self.assertEqual(request('GET', path)[0], 404)
            self.assertEqual(request('GET', '/api/image?sample=valid&kind=sonar'), (200, b'synthetic-image'))
            self.assertEqual(request('GET', '/api/catalog', headers={'Host': 'evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/review', payload(), {'Origin': 'https://evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/review', payload(), {'Origin': 'null'})[0], 403)
            self.assertEqual(request('POST', '/api/review', payload(), {'Sec-Fetch-Site': 'cross-site'})[0], 403)
            self.assertEqual(request('POST', '/api/review', payload(), {'Content-Type': 'text/plain'})[0], 415)
            status, saved = request('POST', '/api/review', payload(), {'Origin': f'http://127.0.0.1:{server.server_port}'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(saved)['review']['reviewer_type'], 'automation_test')
            self.assertEqual(request('POST', '/api/review', payload())[0], 409)
            self.assertEqual(json.loads(request('GET', '/api/export')[1])['event_count'], 1)
        finally:
            server.shutdown();server.server_close();thread.join(3)


class FloorTargetTests(unittest.TestCase):
    def test_only_explicit_floor_identity_selects_floor(self):
        cases = [('2023-09-21_160551', '100lbs_aircraft_bomb', 'target/100lbs_floor'),
                 ('2023-09-20_175000', '100lbs_aircraft_bomb', 'target/100lbs'),
                 ('2023-09-21_100927', 'mortar_shell', 'target/mortar_shell'),
                 ('2023-09-21_120653', 'incindiary_grenade', 'target/incendiary')]
        for recording, category, expected in cases:
            self.assertEqual(service.target_frame_for(dict(recording=recording, category=category)), expected)
        with self.assertRaises(service.APIError):
            service.target_frame_for(dict(recording=service.FLOOR_RECORDING, category='mortar_shell'))

    def test_floor_matrix_and_provenance_do_not_mutate_ordinary_model(self):
        with tempfile.TemporaryDirectory(prefix='sonar-floor-target-test-') as temporary:
            root = Path(temporary)
            directory = root/'100lbs_bomb_(floor)'/service.FLOOR_RECORDING
            directory.mkdir(parents=True)
            (directory/'notes.txt').write_text('- target: 100lbs_bomb (floor)\n', encoding='utf-8')
            yaml_path = root/'official.yaml';yaml_path.write_bytes(b'synthetic official calibration fixture')
            source = service.DatasetSource.__new__(service.DatasetSource)
            source.hash_cache = {};source.rec_dirs = {service.FLOOR_RECORDING: directory}
            source.calibration_version = dict(source=str(yaml_path), sha256=service.sha_bytes(yaml_path.read_bytes()))
            source.fixed_sources = dict(calibration=dict(path='matrix-source',sha256='matrix-hash'),
                                        old_pca=dict(path='frozen-pca-source',sha256='pca-hash'))
            world_floor = service.np.eye(4);world_floor[:3,3] = [1.174003,1.227536,-2.2411]
            mesh_target = service.np.diag([2.,2.,2.,1.]);mesh_target[:3,3] = [.1,.2,.3]
            source.statics = {'target/100lbs_floor':world_floor}
            source.old_model_info = {'100lbs':{'mesh_to_target_similarity':mesh_target.tolist()}}
            original = dict(id='old_pca_fixed', transform=service.np.eye(4), padding=1.)
            original_transform = original['transform'].copy()
            row = dict(recording=service.FLOOR_RECORDING,category='100lbs_aircraft_bomb')
            changed = source.floor_variant(row, original)
            expected = service.np.diag([2.,2.,2.,1.]);expected[:3,3] = [1.274003,1.427536,-1.9411]
            service.np.testing.assert_allclose(changed['transform'],expected,rtol=0,atol=1e-15)
            service.np.testing.assert_array_equal(original['transform'],original_transform)
            self.assertEqual(original['id'],'old_pca_fixed')
            self.assertEqual(changed['id'],'floor_target_pca_fixed')
            self.assertEqual(changed['target_frame'],'target/100lbs_floor')
            self.assertEqual(changed['mesh_to_target_similarity'],mesh_target.tolist())
            self.assertEqual(changed['padding'],1.)
            self.assertEqual(changed['target_mapping_evidence']['notes']['line'],1)
            self.assertEqual(changed['source_hashes']['frozen_mesh_registration'],'pca-hash')
            with self.assertRaises(service.APIError):
                source.floor_variant(dict(recording='2023-09-20_175000',category='100lbs_aircraft_bomb'),original)
            (directory/'notes.txt').write_text('- target: different target\n',encoding='utf-8')
            with self.assertRaises(service.APIError): source.floor_variant(row,original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
