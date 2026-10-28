"""Finite-context mode checks, not research tasks or model success evidence."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import Mock

from jev_anything.chunked import ChunkError, ChunkOptions, RecordStore, choose_chunked
from jev_anything.jev import JevClient, JevConfig
from jev_anything.native import NativeBridgeError, candidates_for, run
from test_document import document


def small_document(serial=1):
    doc = document(serial)
    doc['operations'] = doc['operations'][:2]
    doc['nodes'] = [dict(id=1, parent=None, children=[2, 3], role='Window', label='Workspace', states=[]),
                    dict(id=2, parent=1, children=[4], role='Document', label='Report A', states=[]),
                    dict(id=3, parent=1, children=[5], role='Document', label='Report B', states=[]),
                    dict(id=4, parent=2, children=[], role='Button', label='Remove', states=[]),
                    dict(id=5, parent=3, children=[], role='Button', label='Remove', states=[])]
    doc['text_payloads'] = []
    for op, target in zip(doc['operations'], [4, 5]):
        op['target'] = target
        op['name'] = 'press'
        op['label'] = 'Remove'
        op['label_provenance'] = {'origin': 'public_name', 'source_label': 'Remove',
                                  'display_label': 'Remove', 'source_nodes': [target]}
    return doc


class Stub:
    def __init__(self, decide):
        self.decide = decide
        self.requests = []
        self.raw = []
    def __enter__(self):
        stub = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                payload = json.loads(raw)
                stub.raw.append(raw); stub.requests.append(payload)
                body = json.dumps({'answers': stub.decide(payload)}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.client = JevClient(JevConfig(api_key='chunk-test-only',
                               api_url=f'http://127.0.0.1:{self.server.server_port}/decisions'))
        return self
    def __exit__(self, *args):
        self.server.shutdown(); self.server.server_close(); self.worker.join(timeout=5)


def reader_zero(payload):
    return {key: {'type': 'noul', 'noul': 0} for key in payload['questions']}


class ChunkTests(unittest.TestCase):
    def test_wide_object_keys_roundtrip_links_and_missing_tail(self):
        source={'accessibility':{'nodes':[],'relations':[],'operations':[]},'history':[],
                'candidate_index':{f'op-{i}':{'operation_ref':f'op-{i}'} for i in range(1110)},
                'future':{'字段/a~b'+str(i):[True,1,1.0,None,{},[],'尾部🙂'] for i in range(80)}}
        before=copy.deepcopy(source);store=RecordStore(source,512)
        self.assertEqual(json.dumps(store.reassemble()),json.dumps(source))
        self.assertEqual(source,before)
        self.assertTrue(all(len(json.dumps(r,ensure_ascii=False,separators=(',',':')).encode())<=512 for r in store.records))
        headers=[r for r in store.records if r['kind']=='object' and 'key_count' in r]
        self.assertGreaterEqual(len(headers),2)
        for header in headers:
            rows=store.by_path[header['path']]
            self.assertEqual([k for r in rows[1:] for k in r['keys']],list(source['candidate_index'] if header['path']=='/candidate_index' else source['future']))
            self.assertEqual(store.links(header),{r['id'] for r in rows[1:]}|({store.covering('')} if header['path'] else set()))
            self.assertTrue(all(r['id'] in store.links(header) and header['id'] in store.links(r) for r in rows[1:]))
        rows=store.by_path['/candidate_index'];tail=rows.pop()
        with self.assertRaises(ChunkError):store.reassemble()
        rows.append(tail);saved=rows[1]['offset'];rows[1]['offset']=True
        with self.assertRaises(ChunkError):store.reassemble()
        rows[1]['offset']=saved
        saved=rows[1]['total_keys'];rows[1]['total_keys']=True
        with self.assertRaises(ChunkError):store.reassemble()
        rows[1]['total_keys']=saved
        original=rows[-1]['keys'][-1];rows[-1]['keys'][-1]=rows[1]['keys'][0]
        with self.assertRaises(ChunkError):store.reassemble()
        rows[-1]['keys'][-1]=original
        self.assertEqual(json.dumps(store.reassemble()),json.dumps(source))

    def test_partition_roundtrip_typed_identity_unicode_tail_and_missing_slice(self):
        doc = small_document()
        doc['future'] = {'a/b~c': [True, 1, 1.0, None, {}, [], '🧪尾部' * 1000]}
        source = {'accessibility': doc, 'history': [{'receipt': {'effect': 'unknown'}}]}
        before = copy.deepcopy(source)
        store = RecordStore(source, 512)
        self.assertEqual(json.dumps(store.reassemble()), json.dumps(source))
        self.assertEqual(source, before)
        slices = [r for r in store.records if r['kind'] == 'slice']
        self.assertTrue(any(r['end_of_string'] for r in slices))
        victim = slices[0]; original_length = victim['total_length']; victim['total_length'] = True
        with self.assertRaises(ChunkError): store.reassemble()
        victim['total_length'] = original_length
        other = copy.deepcopy(source); other['accessibility']['generation'] = True
        self.assertNotEqual(RecordStore(other, 512).source_sha256, store.source_sha256)
        path = next(r['path'] for r in store.records if r['kind'] == 'string')
        store.by_path[path].pop()
        with self.assertRaises(ChunkError): store.reassemble()

    def test_actual_requests_cover_all_source_and_keep_251_candidates_in_one_final(self):
        doc = document(); before = copy.deepcopy(doc); events = []
        candidates = candidates_for(doc, ['literal A', 'literal B'])
        history = [{'operation': {'id': 'past'}, 'receipt': {'effect': 'unknown', 'readback': {'text': '全部历史'}}}]
        def decide(payload):
            if 'records' in payload['state']: return reader_zero(payload)
            return {'action': {'type': 'choice', 'choice': 'edit-p1'},
                    'inspect': {'type': 'choice', 'choice': 'none'}}
        with Stub(decide) as stub:
            answer = choose_chunked(stub.client, 'Read then select', doc, candidates, history, emit=events.append)
        self.assertEqual(answer['choice'], 'edit-p1')
        readers = [p for p in stub.requests if 'records' in p['state']]
        finals = [p for p in stub.requests if 'operation_definitions' in p['state']]
        self.assertEqual(len(finals), 1)
        self.assertTrue(all(len(p['questions']) <= 24 for p in readers))
        self.assertTrue(all(len(raw) <= 60000 for raw in stub.raw))
        store = RecordStore({'accessibility': doc, 'history': history}, 8192)
        self.assertEqual([r for p in readers for r in p['state']['records']], store.records)
        final = finals[0]
        self.assertEqual(list(final['questions']['action']['criteria']), [c['id'] for c in candidates] + ['done', 'abstain', 'wait'])
        self.assertEqual(final['state']['history'], history)
        self.assertEqual(final['state']['source_completeness'], doc['completeness'])
        self.assertEqual(final['state']['readable_scope'], doc['readable_scope'])
        self.assertTrue(final['state']['coverage']['all_source_records_read'])
        self.assertTrue(final['state']['coverage']['selection_lossy'])
        self.assertEqual(doc, before)
        self.assertFalse(any('action' in p['questions'] for p in readers))

    def test_cross_record_inspection_ignores_done_until_evidence_repaired(self):
        doc = small_document(); events = []; final_count = 0
        for node in doc['nodes']: node['description'] = 'Public contextual detail ' * 5
        def decide(payload):
            nonlocal final_count
            state = payload['state']
            if 'records' in state:
                return {r['id']: {'type': 'noul', 'noul': float(r['path'] == '/accessibility/nodes/2')}
                        for r in state['records']}
            final_count += 1
            if final_count == 1:
                refs = [k for k in payload['questions']['inspect']['criteria'] if k != 'none']
                self.assertTrue(refs)
                return {'action': {'type': 'choice', 'choice': 'done'},
                        'inspect': {'type': 'choice', 'choice': refs[0]}}
            return {'action': {'type': 'choice', 'choice': 'op-1'},
                    'inspect': {'type': 'choice', 'choice': 'none'}}
        options = ChunkOptions(record_bytes=1024, max_questions=1)
        with Stub(decide) as stub:
            answer = choose_chunked(stub.client, 'Report B', doc, candidates_for(doc), [], options=options, emit=events.append)
        self.assertEqual(answer['choice'], 'op-1')
        self.assertEqual(final_count, 2)
        self.assertEqual(next(e for e in events if e['kind']=='chunk_inspect')['ignored_action'], 'done')

    def test_invalid_reader_never_reaches_final_or_gui(self):
        doc = small_document(); bridge = Mock(snapshot=Mock(return_value=doc))
        for bad in [True, float('nan'), 2, 'done']:
            class Bad:
                model = 'stub'; metadata = {}
                def decide(self, *, state, questions):
                    return {q: {'type': 'noul', 'noul': bad} for q in questions}
            result = run('Read', bridge, Bad(), decision_mode='chunk-evidence')
            self.assertEqual(result['decision_error_kind'], 'invalid_evidence')
        bridge.execute.assert_not_called()

    def test_budget_failure_does_not_trim_or_dispatch_or_call_provider(self):
        doc = small_document(); history = [{'receipt': {'text': '完整历史' * 20000}}]
        provider = Mock(model='stub'); events = []
        with self.assertRaises(ChunkError) as caught:
            choose_chunked(provider, 'Read', doc, candidates_for(doc), history, emit=events.append)
        self.assertEqual(caught.exception.kind, 'final_base_overflow')
        provider.decide.assert_not_called()
        self.assertEqual(events[0]['source']['history'], history)

    def test_refinement_exhaustion_does_not_release_done(self):
        doc = small_document(); bridge = Mock(snapshot=Mock(return_value=doc))
        class Fake:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'records' in state: return reader_zero({'questions': questions})
                record = next(k for k in questions['inspect']['criteria'] if k != 'none')
                return {'action': {'type': 'choice', 'choice': 'done'},
                        'inspect': {'type': 'choice', 'choice': record}}
        result = run('Read', bridge, Fake(), decision_mode='chunk-evidence',
                     chunk_options=ChunkOptions(max_refinements=0))
        self.assertEqual(result['decision_error_kind'], 'refinement_limit')
        bridge.execute.assert_not_called()
        self.assertIsNone(result['task_completed'])

    def test_not_attempted_restarts_all_reading_and_unknown_is_not_replayed(self):
        decisions = []
        class Fake:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'records' in state: return reader_zero({'questions': questions})
                decisions.append(state['source_sha256'])
                return {'action': {'type': 'choice', 'choice': 'op-0'}, 'inspect': {'type': 'choice', 'choice': 'none'}}
        bridge = Mock(snapshot=Mock(side_effect=[small_document(1), small_document(2), small_document(3)]),
                      execute=Mock(side_effect=[NativeBridgeError({'delivery': 'not_attempted', 'error': 'stale'}),
                                                {'accepted': True, 'effect': 'unknown'}]))
        result = run('Remove', bridge, Fake(), decision_mode='chunk-evidence')
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(bridge.execute.call_count, 2)
        self.assertEqual(len(decisions), 2)
        self.assertNotEqual(decisions[0], decisions[1])
        self.assertEqual(result['history'][0]['receipt']['delivery'], 'not_attempted')
