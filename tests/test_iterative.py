"""Model results, not old raw text, flow across a complete one-operation scan."""
import copy
import json
import unittest
from unittest.mock import Mock

from jev_anything.chunked import ChunkError, ChunkOptions, RecordStore, choose_chunked
from jev_anything.iterative import choose_iterative, _catalog_wire, _catalog_wire_v3, _catalog_labels, _catalog_rows, _previous_wire
from jev_anything.jev import JevError
from jev_anything.record_wire import unpack
from jev_anything.native import NativeBridgeError, candidates_for, run
from jev_anything.document import public_text_comparison
from test_chunked import Stub, small_document
from test_document import document, identity_document, remap_snapshot_ids
from jev_anything.document import public_source_identity, public_focus_selection, focus_selection_wire, expand_focus_selection, _expand_column, _compact_column_v2


def proposal(key):
    return {'proposal':{'type':'choice','choice':key}}


def reviewed(key):
    return {'final_decision':{'type':'choice','choice':key}}


def routed_proposal(key,state,questions):
    if 'kind' in questions:
        if key in ('done','abstain','wait'):return {'kind':{'type':'choice','choice':key}}
        catalog=state['candidate_catalog'];row=next(r for r in catalog['rows'] if r[0]==key)
        kind=catalog['symbols']['kind'][row[1]]
        return {'kind':{'type':'choice','choice':'kind/'+kind}}
    if 'branch' in questions:
        catalog=state['candidate_catalog'];kind=state['conditional_on']['kind']
        ids=[r[0] for r in catalog['rows'] if catalog['symbols']['kind'][r[1]]==kind]
        branch=next(k for k,v in questions['branch']['criteria'].items() if k!='abstain'
                    and ids.index(json.loads(v)['first_candidate'])<=ids.index(key)<=ids.index(json.loads(v)['last_candidate']))
        return {'branch':{'type':'choice','choice':branch}}
    return proposal(key)


def evaluation(verdict='supported',support=.8,goal_status='pending'):
    return {'assessment':{'type':'choice','choice':'complete' if goal_status=='achieved' else verdict},
            'support':{'type':'noul','noul':support}}


class IterativeTests(unittest.TestCase):
    def test_tight_frame_repartitions_long_text_without_losing_any_record(self):
        doc = small_document()
        body = 'ABCDEΩ' * 3000 + 'PUBLIC TAIL'
        doc['text_payloads'] = [{'source': 4, 'read': {'status': 'complete', 'text': body}}]
        class Complete:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'proposal' in questions: return proposal('done')
                return evaluation(goal_status='achieved')
        events = []
        answer = choose_iterative(Complete(), 'A task', doc, candidates_for(doc), [],
            options=ChunkOptions(max_request_bytes=15000), emit=events.append,
            terminal_policy='accumulated', planning_experiment={'preparatory_steps': False, 'repair_rounds': 0,
                'current_state': True, 'state_encoding': 'columns', 'public_evidence': True})
        source = next(e for e in events if e['kind'] == 'iterative_source')
        self.assertLess(source['options']['record_bytes'], 4096)
        store = RecordStore(source['source'], source['options']['record_bytes'])
        requests = [e for e in events if e['kind'] == 'iterative_request']
        self.assertTrue(all(e['request_bytes'] <= 15000 for e in requests))
        self.assertEqual([r for e in requests if e['stage'] == 'propose'
                          for r in unpack(e['state']['current_records'])], store.records)
        self.assertEqual(store.reassemble()['accessibility']['text_payloads'][0]['read']['text'], body)
        self.assertEqual(answer['choice'], 'done')

    def test_global_focus_columns_keep_every_row_when_state_changes_fragment_runs(self):
        doc = small_document(); doc['operations'] = []
        for i in range(10, 1010):
            doc['nodes'].append({'id':i,'parent':1,'role':'MenuItem','label':None if i%11 else f'Ω {i}',
                                 'states':['Selected'] if i%2 else ['Focused'], 'partial':i%7 == 0})
            doc['operations'].append({'id':f'opaque-{i}', 'target':i, 'kind':'selection', 'selected':True, 'agent_invocable':True})
        wire = focus_selection_wire(doc, 'complete_columns')
        self.assertEqual(wire['version'], 'jev.public-focus-selection.v6')
        self.assertEqual(expand_focus_selection(wire), public_focus_selection(doc))

    def test_extended_columns_preserve_mixed_ids_padding_unicode_and_typed_values(self):
        columns = [
            [f'{i}' for i in range(700)] + [f'{i}-p0' for i in range(700, 900)] + ['Ω/non-number', None, False, 0],
            [f'opaque/{i:04d}/Ω' for i in range(30, 400)],
            [i//3 for i in range(1200)],
            [True if i % 17 else 1 for i in range(600)] + [None, 'null', False, 0],
        ]
        for values in columns:
            with self.subTest(values=values[:3]):
                wire = _compact_column_v2(values)
                self.assertEqual(json.dumps(_expand_column(wire), ensure_ascii=False), json.dumps(values, ensure_ascii=False))
                self.assertLess(len(json.dumps(wire)), len(json.dumps(values)))

    def test_shared_catalog_labels_resolve_in_the_same_request_without_changing_bindings(self):
        labels = [None] + [f'公開 label {i}: ' + 'long public context Ω '*4 for i in range(200)]
        focus = {'node_symbols': {'label': labels}}
        catalog = {'columns': ['candidate_id', 'kind_symbol', 'name_symbol', 'label_symbol', 'target_ref'],
                   'symbols': {'kind': ['action'], 'name': ['click'], 'label': labels + ['extra public label']},
                   'rows': [[f'opaque/{i:04d}-p0', 0, 0, i % 202, i//3] for i in range(1000)],
                   'bindings': {'opaque/0999-p0': {'operation_ref': 'canonical Ω', 'parameter': {'text': 'exact\nΩ'}}}}
        original = copy.deepcopy(catalog)
        wire = _catalog_wire_v3(catalog, focus)
        self.assertEqual(wire['encoding'], 'jev.candidate-columns.v3')
        self.assertEqual(wire['symbols']['label']['encoding'], 'focus_label_refs')
        self.assertEqual(_catalog_rows(wire), catalog['rows'])
        self.assertEqual(_catalog_labels(wire, focus), catalog['symbols']['label'])
        self.assertEqual(wire['bindings'], catalog['bindings'])
        self.assertEqual(catalog, original)
        self.assertLess(len(json.dumps(wire)), len(json.dumps(_catalog_wire(catalog))))

    def test_extended_column_decoder_rejects_overlapping_positions_and_invalid_counts(self):
        for malformed in [
            {'encoding':'default_positions', 'length':2, 'default':None,
             'values':[['a', {'encoding':'literal','values':[0]}], ['b', {'encoding':'literal','values':[0]}]]},
            {'encoding':'run_columns', 'values':[{'encoding':'literal','values':['a']}, {'encoding':'literal','values':[True]}]},
            {'encoding':'run_columns', 'values':[{'encoding':'literal','values':['a']}, {'encoding':'literal','values':[]}]},
        ]:
            with self.assertRaises(ValueError):
                _expand_column(malformed)

    def test_compact_focus_columns_reconstruct_all_current_flags_labels_refs_and_partial(self):
        doc = small_document(); doc['operations'] = []
        for i in range(6, 506):
            doc['nodes'].append({'id': i, 'parent': 1, 'children': [], 'role': 'MenuItem',
                'label': None if i == 101 else f'Public Ω {i}', 'states': ['Selected'] if i == 7 else [], 'partial': i == 10})
            doc['operations'].append({'id': f'opaque/{i}', 'target': i, 'kind': 'selection', 'selected': True, 'agent_invocable': True})
        original = public_focus_selection(doc); wire = focus_selection_wire(doc, 'compact_columns')
        self.assertEqual(wire['version'], 'jev.public-focus-selection.v5')
        rows = []
        for run in wire['nodes']:
            for row in zip(*[_expand_column(c) for c in run['column_values']]):
                rows.append({**{f: wire['node_symbols'][f][v] if f in wire['node_symbols'] else v
                    for f,v in zip(wire['node_columns'], row)},
                    'observed_state_flags': run['observed_state_flags'], 'source_partial': run['source_partial']})
        self.assertEqual(json.dumps(rows), json.dumps(original['nodes']))
        self.assertLess(len(json.dumps(wire)), len(json.dumps(focus_selection_wire(doc, 'columns'))))

    def test_probability_columns_preserve_every_zero_key_value_and_prior_result_field(self):
        probabilities = {f'opaque/Ω-{i:04d}': 0 if i != 179 else .8200000000000001 for i in range(220)}
        answer = {'type':'choice','choice':'opaque/Ω-0179','probabilities':probabilities,'confidence':.82}
        original = {'proposal':dict(answer, steps=[{'stage':'public_fields','answer':answer}]),
                    'evaluation':{'assessment':answer,'support':{'type':'noul','noul':.9}},
                    'effective_assessment':answer,'binding':{'assessment':answer,'candidate_id':'actual-id'},
                    'public_source':{'node':{'id':7,'value':'canonical public value'},'text_payloads':[]}}
        wire = _previous_wire(original)
        def expand(value):
            if isinstance(value, list): return [expand(v) for v in value]
            if isinstance(value, dict):
                if value.get('encoding') in ('jev.probability-columns.v1','jev.probability-columns.v2'):
                    keys = ([value['key_prefix']+s for s in value['key_suffixes']] if value['encoding'].endswith('.v1') else
                            [value['key_prefixes'][i]+s for i,s in zip(_expand_column(value['prefix_indexes']), value['key_suffixes'])])
                    return dict(zip(keys, _expand_column(value['values'])))
                return {k:expand(v) for k,v in value.items()}
            return value
        self.assertEqual(json.dumps(expand(wire)), json.dumps(original))
        self.assertEqual(wire['proposal']['choice'], original['proposal']['choice'])
        self.assertEqual(wire['public_source'], original['public_source'])
        self.assertLess(len(json.dumps(wire)), len(json.dumps(original)))

    def test_candidate_columns_preserve_opaque_ids_order_and_typed_fields(self):
        catalog = {'columns': ['candidate_id', 'kind_symbol', 'name_symbol', 'label_symbol', 'target_ref'],
            'symbols': {'kind': ['action'], 'name': [None], 'label': ['Ω']},
            'rows': [[f'opaque/Ω-{i:04d}-x', 0, 0, 0, i] for i in range(300)],
            'bindings': {}, 'binding_default': 'operation_ref equals candidate_id unless overridden'}
        wire = _catalog_wire(catalog)
        self.assertEqual(_catalog_rows(wire), catalog['rows'])
        self.assertLess(len(json.dumps(wire)), len(json.dumps(catalog)))
        self.assertEqual(wire['bindings'], catalog['bindings'])
        self.assertEqual(wire['symbols'], catalog['symbols'])

    def test_conditional_prefix_and_member_keep_canonical_target_sources_for_all_legal_members(self):
        doc = small_document()
        doc['operations'] = [dict(doc['operations'][0], id=f'opaque-{i}') for i in range(260)]
        doc['nodes'].append(dict(id=6, parent=1, children=[], role='TextInput', label='Search', states=[]))
        for source, label, text in [(4, None, 'Object A'), (5, None, 'Object B'), (6, 'Search', '')]:
            next(n for n in doc['nodes'] if n['id'] == source).update(role='TextInput', label=label, value=text)
            doc['text_payloads'].append({'source': source, 'read': {'status': 'complete', 'text': text}})
        for key, source, label in [('edit-a', 4, 'Unnamed TextInput'), ('edit-b', 5, 'Unnamed TextInput'), ('search', 6, 'Search')]:
            doc['operations'].append({'id': key, 'target': source, 'kind': 'replace_text', 'label': label,
                'parameter': 'text', 'parameter_domain': {'kind': 'text'}, 'agent_invocable': True})
        class Evidence:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'kind' in questions:
                    assert len(_catalog_rows(state['candidate_catalog'])) == 263
                    return {'kind': {'type': 'choice', 'choice': 'kind/replace_text'}}
                if 'public_fields' in questions:
                    sources = state['conditional_public_sources']
                    assert {o['id'] for o in sources['operations']} == {'edit-a', 'edit-b', 'search'}
                    assert {p['node']['id'] for p in sources['sources']} == {4, 5, 6}
                    key = next(k for k,v in questions['public_fields']['criteria'].items()
                               if k != 'abstain' and dict(json.loads(v)[0]).get(1) == 'Unnamed TextInput')
                    return {'public_fields': {'type': 'choice', 'choice': key}}
                if 'proposal' in questions:
                    assert {p['node']['id'] for p in state['conditional_public_sources']['sources']} == {4, 5}
                    return proposal('edit-b-p0')
                return evaluation()
        result = choose_iterative(Evidence(), 'Replace Object B', doc, candidates_for(doc, ['literal']), [],
            terminal_policy='accumulated', planning_experiment={'preparatory_steps': False, 'repair_rounds': 0,
                'current_state': True, 'state_encoding': 'columns', 'public_evidence': True})
        self.assertEqual(result['choice'], 'edit-b-p0')

    def test_large_optional_target_duplicate_never_becomes_a_source_size_limit(self):
        doc = small_document(); target = doc['operations'][0]['target']
        body = 'long public body\n' * 6000 + 'PUBLIC TAIL Ω'
        next(n for n in doc['nodes'] if n['id'] == target)['value'] = body
        doc['text_payloads'] = [{'source': target, 'read': {'status': 'complete', 'text': body}}]
        objects = {'version': 'jev.public-object-comparison.v1', 'before_observation_id': 0,
            'after_observation_id': doc['observation_id'],
            **{k: doc[k] for k in ('session', 'generation', 'interaction_scope', 'readable_scope')},
            'changed': [{'locator_ref': 'public-ref', 'before': {'label': 'public header ' * 6000}, 'after': None}],
            'is_execution_authority': False, 'independent_task_completion': 'not_assessed'}
        history = [{'operation': {}, 'receipt': {}, 'client_public_object_comparison': objects}]
        events = []
        class Evidence:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'proposal' in questions: return proposal('op-0')
                assert state['proposed_public_source']['repeat_status'] == 'source_records_only'
                assert state['proposed_public_source']['node_ref'] == target
                assert state['latest_execution_evidence']['public_object_comparison']['repeat_status'] == 'source_records_only'
                return evaluation()
        answer = choose_iterative(Evidence(), 'A public task', doc, candidates_for(doc), history,
            terminal_policy='accumulated', emit=events.append,
            planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'current_state': True,
                                 'state_encoding': 'columns', 'public_evidence': True})
        self.assertEqual(answer['choice'], 'op-0')
        store = RecordStore(events[0]['source'], events[0]['options']['record_bytes'])
        roots = [e for e in events if e['kind'] == 'iterative_request' and e['stage'] == 'propose']
        self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])], store.records)
        self.assertEqual(store.reassemble()['accessibility'], doc)
        self.assertEqual(store.reassemble()['history'], history)
        self.assertEqual(store.reassemble()['accessibility']['text_payloads'][0]['read']['text'], body)

    def test_explicit_public_evidence_repeats_exact_current_target_payload_without_pruning_source(self):
        doc = small_document(); target = doc['operations'][0]['target']
        doc['nodes'][3]['label'] = None
        doc['text_payloads'] = [{'source': target, 'read': {'status': 'complete', 'text': 'Current object Ω\nfull body'}}]
        doc['future_public_text'] = 'other complete source material\n' * 4000
        events = []
        class Evidence:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                if 'proposal' in questions: return proposal('op-0')
                self_source = state['proposed_public_source']
                assert self_source['node'] == next(n for n in doc['nodes'] if n['id'] == target)
                assert self_source['text_payloads'] == doc['text_payloads']
                if state['previous_result'] is not None:
                    previous = state['previous_result']
                    if 'encoding' in previous: previous = unpack(previous)[0]
                    assert previous['public_source'] == self_source
                return evaluation()
        answer = choose_iterative(Evidence(), 'A public task', doc, candidates_for(doc), [],
            terminal_policy='accumulated', emit=events.append,
            planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'current_state': True,
                                 'state_encoding': 'columns', 'public_evidence': True})
        self.assertEqual(answer['choice'], 'op-0')
        store = RecordStore(events[0]['source'], events[0]['options']['record_bytes'])
        roots = [e for e in events if e['kind'] == 'iterative_request' and e['stage'] == 'propose']
        self.assertGreater(len(roots), 1)
        self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])], store.records)

    def test_current_state_columns_use_finer_complete_source_framing(self):
        doc = small_document(); doc['future_public_text'] = ''.join(f'完整原文{i:05d};' for i in range(12000))
        events = []
        class Complete:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                return proposal('done') if 'proposal' in questions else evaluation('complete')
        answer = choose_iterative(Complete(), 'A public goal', doc, candidates_for(doc), [],
            terminal_policy='accumulated', emit=events.append,
            planning_experiment={'preparatory_steps': False, 'repair_rounds': 0,
                                 'current_state': True, 'state_encoding': 'columns'})
        source = events[0]
        self.assertEqual(source['options']['record_bytes'], 4096)
        store = RecordStore(source['source'], 4096)
        self.assertEqual(store.reassemble()['accessibility'], doc)
        roots = [e for e in events if e['kind'] == 'iterative_request' and e['stage'] == 'propose']
        self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])], store.records)
        self.assertEqual(answer['choice'], 'done')

    def test_focus_selection_columns_preserve_every_typed_value_and_source(self):
        doc = small_document()
        for op in doc['operations']: op['kind'] = 'selection'
        doc['nodes'][3].update(label=None, states=['Selected', 'Focused'], partial=False)
        doc['nodes'][4].update(label='公开值 Ω', states=[], partial=True)
        original = copy.deepcopy(doc)
        plain = public_focus_selection(doc); wire = focus_selection_wire(doc, 'columns')
        restored = {**wire, 'version': 'jev.public-focus-selection.v1',
                    'nodes': [{**{field: wire['node_symbols'][field][value] if field in wire['node_symbols'] else value
                                  for field, value in zip(wire['node_columns'], row)},
                               'observed_state_flags': run['observed_state_flags'], 'source_partial': run['source_partial']}
                              for run in wire['nodes'] for row in run['rows']]}
        del restored['node_columns']
        del restored['node_symbols']
        self.assertEqual(restored, plain); self.assertEqual(doc, original)
        self.assertEqual(focus_selection_wire(doc), plain)

    def test_native_current_state_mode_executes_only_the_returned_current_candidate(self):
        before = small_document(); after = small_document(2)
        for doc in (before, after):
            for op in doc['operations']: op['kind'] = 'selection'; op['selected'] = True
            for n in doc['nodes']: n['partial'] = False
        before['nodes'][3]['states'] = ['Selected']
        after['nodes'][4]['states'] = ['Selected']
        bridge = Mock(snapshot=Mock(side_effect=[before, after]),
                      execute=Mock(return_value={'accepted': True, 'effect': 'confirmed', 'readback': {'selected': True}}))
        class CurrentState:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                bridge.execute.assert_not_called()
                assert state['current_focus_selection']['observation_id'] == before['observation_id']
                return proposal('op-1') if 'proposal' in questions else evaluation()
        result = run('A multi-step public goal', bridge, CurrentState(), max_steps=1,
                     decision_mode='iterative-current-state')
        self.assertEqual(result['status'], 'step_limit'); self.assertIsNone(result['task_completed'])
        self.assertEqual(bridge.execute.call_count, 1)
        actual_doc, actual_candidate = bridge.execute.call_args.args
        self.assertEqual(actual_doc, before); self.assertEqual(actual_candidate['id'], 'op-1')
        self.assertEqual(actual_candidate['target'], 5)

    def test_current_selection_is_available_in_every_chunk_and_is_not_requested_selection(self):
        doc = small_document()
        for op in doc['operations']:
            op['kind'] = 'selection'; op['selected'] = True
        doc['nodes'][3]['states'] = ['Selected', 'Focused']; doc['nodes'][3]['partial'] = False
        doc['nodes'][4]['states'] = []; doc['nodes'][4]['partial'] = False
        doc['future_public_text'] = ''.join(f'public record {i:04d};' for i in range(2000))
        original = copy.deepcopy(doc); events = []
        expected = public_focus_selection(doc)
        byid = {n['source']: n for n in expected['nodes']}
        self.assertEqual(byid[4]['observed_state_flags'], ['Selected', 'Focused'])
        self.assertEqual(byid[5]['observed_state_flags'], [])
        class CurrentState:
            model = 'stub'; metadata = {}
            def decide(self, *, state, questions):
                assert state['current_focus_selection'] == expected
                if 'proposal' in questions:
                    assert 'REQUESTED state' in questions['proposal']['instructions']
                    assert json.loads(questions['proposal']['criteria']['op-1'])['selected'] is True
                    return proposal('op-1')
                assert state['proposed_operation']['operation']['selected'] is True
                return evaluation()
        answer = choose_iterative(CurrentState(), 'Select the requested object', doc, candidates_for(doc), [],
            terminal_policy='accumulated', options=ChunkOptions(max_request_bytes=24000, record_bytes=1024), emit=events.append,
            planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'current_state': True})
        self.assertEqual(answer['choice'], 'op-1'); self.assertEqual(doc, original)
        source = events[0]; roots = [e for e in events if e['kind'] == 'iterative_request' and e['stage'] == 'propose']
        self.assertGreater(len(roots), 1)
        self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])],
                         RecordStore(source['source'], source['options']['record_bytes']).records)

    def test_current_selection_preserves_partial_and_rejects_redacted_source(self):
        doc = small_document(); doc['operations'][1]['kind'] = 'selection'
        doc['nodes'][4]['partial'] = True
        row = next(r for r in public_focus_selection(doc)['nodes'] if r['source'] == 5)
        self.assertTrue(row['source_partial']); self.assertEqual(row['observed_state_flags'], [])
        doc['nodes'][4]['redacted'] = True
        with self.assertRaises(ValueError): public_focus_selection(doc)
        with self.assertRaises(ValueError):
            choose_iterative(Mock(), 'goal', doc, [], [], terminal_policy='accumulated',
                planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'current_state': 'true'})

    def test_diagnostic_memory_is_model_result_only_and_log_ablation_is_explicit(self):
        doc = small_document()
        doc['future_public_text'] = ''.join(f'public record {i:04d};' for i in range(2000))
        for memory in ('off', 'log', 'carry'):
            with self.subTest(memory=memory):
                events = []
                class Diagnostic:
                    model = 'stub'; metadata = {}
                    def decide(self, *, state, questions):
                        if 'proposal' in questions:
                            if 'planning_repair' in state:
                                assert unpack(state['current_records']) == []
                            remembered = state['previous_result']
                            if remembered:
                                assert ('diagnostic_reason' in remembered) == (memory == 'carry')
                                assert ('diagnostic_reason' in remembered['evaluation']) == (memory == 'carry')
                            return proposal('op-0')
                        previous = state['previous_result']
                        answer = evaluation('contradicted' if previous is None else 'keep_previous')
                        if 'diagnostic_reason' in questions:
                            answer['diagnostic_reason'] = {'type': 'choice', 'choice':
                                'target_mismatch' if previous is None else 'unchanged_no_relevant_evidence'}
                        return answer
                answer = choose_iterative(Diagnostic(), 'A public goal', doc, candidates_for(doc), [],
                    terminal_policy='accumulated', options=ChunkOptions(max_request_bytes=24000, record_bytes=1024), emit=events.append,
                    planning_experiment={'preparatory_steps': False, 'repair_rounds': 1, 'diagnostic_reason': memory})
                self.assertEqual(answer['choice'], 'abstain')
                source = events[0]
                progress = [e for e in events if e['kind'] == 'iterative_progress']
                self.assertGreater(len(progress), 1)
                self.assertEqual([r for e in progress for r in e['evaluated_record_ids']],
                                 [r['id'] for r in RecordStore(source['source'], source['options']['record_bytes']).records])
                if memory != 'off':
                    self.assertTrue(all(e['result']['diagnostic_reason']['choice'] == 'target_mismatch' for e in progress))
                self.assertEqual(len([e for e in events if e['kind'] == 'iterative_repair_progress']), 1)
                self.assertEqual(len([e for e in events if e['kind'] == 'iterative_release']), 1)

    def test_diagnostic_reason_is_validated_and_never_overrides_the_assessment(self):
        for reason, invalid in [('supported_next_step', False), ('invented_reason', True)]:
            events = []
            class Diagnostic:
                model = 'stub'; metadata = {}
                def decide(self, *, state, questions):
                    if 'proposal' in questions: return proposal('op-0')
                    return {**evaluation('contradicted'), 'diagnostic_reason': {'type': 'choice', 'choice': reason}}
            if invalid:
                with self.assertRaises(ChunkError):
                    choose_iterative(Diagnostic(), 'goal', small_document(), candidates_for(small_document()), [],
                        terminal_policy='accumulated', emit=events.append,
                        planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'diagnostic_reason': 'carry'})
                self.assertFalse(any(e['kind'] == 'iterative_release' for e in events))
            else:
                answer = choose_iterative(Diagnostic(), 'goal', small_document(), candidates_for(small_document()), [],
                    terminal_policy='accumulated', emit=events.append,
                    planning_experiment={'preparatory_steps': False, 'repair_rounds': 0, 'diagnostic_reason': 'carry'})
                self.assertEqual(answer['choice'], 'abstain')

    def test_planning_repair_is_bounded_and_only_follows_a_complete_unsupported_scan(self):
        for initial, repaired in [('contradicted', 'supported'), ('insufficient', 'contradicted'),
                                  ('supported', None), ('complete', None), ('wait', None)]:
            with self.subTest(initial=initial, repaired=repaired):
                doc = small_document(); events = []
                class Planning:
                    model = 'stub'; metadata = {}
                    def decide(self, *, state, questions):
                        repair = 'planning_repair' in state
                        if 'proposal' in questions:
                            return proposal('op-1' if repair else 'op-0')
                        return evaluation(repaired if repair else initial)
                answer = choose_iterative(Planning(), 'A public multi-step goal', doc,
                    candidates_for(doc), [], terminal_policy='accumulated', emit=events.append,
                    planning_experiment={'preparatory_steps': False, 'repair_rounds': 1})
                source = next(e for e in events if e['kind'] == 'iterative_source')
                requests = [e for e in events if e['kind'] == 'iterative_request']
                roots = [e for e in requests if e['stage'] == 'propose']
                scan = [e for e in roots if 'planning_repair' not in e['state']]
                self.assertEqual([r for e in scan for r in unpack(e['state']['current_records'])],
                    RecordStore(source['source'], source['options']['record_bytes']).records)
                repairs = [e for e in roots if 'planning_repair' in e['state']]
                self.assertEqual(len(repairs), int(repaired is not None))
                if repairs:
                    self.assertEqual(unpack(repairs[0]['state']['current_records']), [])
                    self.assertTrue(repairs[0]['state']['progress']['all_records_evaluated_if_this_round_succeeds'])
                    last_scan = [e for e in events if e['kind'] == 'iterative_progress'][-1]
                    self.assertEqual(repairs[0]['state']['previous_result'], last_scan['result'])
                    self.assertEqual(len([e for e in events if e['kind'] == 'iterative_repair_progress']), 1)
                expected = {'complete': 'done', 'wait': 'wait', 'supported': 'op-0'}.get(initial,
                    'op-1' if repaired == 'supported' else 'abstain')
                self.assertEqual(answer['choice'], expected)
                self.assertEqual(len([e for e in events if e['kind'] == 'iterative_release']), 1)

    def test_planning_wording_preserves_all_facts_candidates_and_strict_binding(self):
        doc = small_document(); candidates = candidates_for(doc)
        sources = []
        for wording in (False, True):
            events = []
            class Planning:
                model = 'stub'; metadata = {}
                def decide(self, *, state, questions):
                    if 'proposal' in questions:
                        assert set(questions['proposal']['criteria']) == {c['id'] for c in candidates} | {'done', 'abstain', 'wait'}
                        return proposal('op-1')
                    assert state['proposed_operation']['candidate_id'] == 'op-1'
                    assert state['proposed_operation']['operation']['target'] == 5
                    assert ('preparatory operation' in questions['assessment']['criteria']['supported']) == wording
                    return evaluation()
            answer = choose_iterative(Planning(), 'A public multi-step goal', doc, candidates, [],
                terminal_policy='accumulated', emit=events.append,
                planning_experiment={'preparatory_steps': wording, 'repair_rounds': 0})
            self.assertEqual(answer['choice'], 'op-1')
            sources.append(next(e['source'] for e in events if e['kind'] == 'iterative_source'))
        self.assertEqual(sources[0], sources[1])
        for config in ({'preparatory_steps': True, 'repair_rounds': 2},
                       {'preparatory_steps': True, 'repair_rounds': True}, {}):
            with self.assertRaises(ValueError):
                choose_iterative(Mock(), 'goal', doc, candidates, [], terminal_policy='accumulated',
                    planning_experiment=config)

    def test_accumulated_terminal_waits_for_all_records_before_model_done_or_one_write(self):
        for verdict in ('complete', 'supported'):
            with self.subTest(verdict=verdict):
                doc=small_document();doc['future_public_text']=''.join(f'公开记录{i:05d};' for i in range(16000))
                bridge=Mock(snapshot=Mock(side_effect=[doc,small_document(2)]),
                            execute=Mock(return_value={'accepted':True,'effect':'confirmed'}))
                events=[]
                class Accumulated:
                    model='stub';metadata={}
                    def decide(self,*,state,questions):
                        bridge.execute.assert_not_called()
                        assert 'final_decision' not in questions
                        return proposal('op-0') if 'proposal' in questions else evaluation(verdict)
                result=run('The public GUI goal',bridge,Accumulated(),max_steps=1,
                           decision_mode='iterative-accumulated',emit=events.append)
                self.assertEqual(result['status'],'model_completed' if verdict=='complete' else 'step_limit')
                self.assertIsNone(result['task_completed'])
                self.assertEqual(bridge.execute.call_count,0 if verdict=='complete' else 1)
                source=next(e for e in events if e['kind']=='iterative_source')
                roots=[e for e in events if e['kind']=='iterative_request' and e['stage']=='propose']
                self.assertGreater(len(roots),1)
                self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])],
                                 RecordStore(source['source'],source['options']['record_bytes']).records)
                releases=[e for e in events if e['kind']=='iterative_release']
                self.assertEqual(len(releases),1)
                self.assertTrue(releases[0]['all_source_records_evaluated'])

    def test_accumulated_terminal_revokes_early_complete_and_never_trusts_proposal_done(self):
        for scenario in ('late_contradiction','unsupported_done'):
            with self.subTest(scenario=scenario):
                doc=small_document();doc['future_public_text']=''.join(f'后续证据{i:05d};' for i in range(16000))
                bridge=Mock(snapshot=Mock(return_value=doc));events=[]
                class Contrary:
                    model='stub';metadata={}
                    def decide(self,*,state,questions):
                        bridge.execute.assert_not_called()
                        assert 'final_decision' not in questions
                        if 'proposal' in questions:
                            return proposal('done' if scenario=='unsupported_done' else 'op-0')
                        if scenario=='unsupported_done':return evaluation('supported')
                        last=state['progress']['all_records_evaluated_if_this_round_succeeds']
                        return evaluation('contradicted' if last else 'complete')
                result=run('Unresolved goal conditions',bridge,Contrary(),
                           decision_mode='iterative-accumulated',emit=events.append)
                self.assertEqual(result['status'],'abstained');self.assertIsNone(result['task_completed'])
                bridge.execute.assert_not_called()
                progress=[e for e in events if e['kind']=='iterative_progress']
                self.assertGreater(len(progress),1)
                if scenario=='late_contradiction':
                    self.assertEqual(progress[0]['result']['effective_assessment']['choice'],'complete')
                    self.assertEqual(progress[-1]['result']['effective_assessment']['choice'],'contradicted')

    def test_locator_readback_uses_current_source_without_executing_a_rebound_reference(self):
        before=identity_document();after=remap_snapshot_ids(before);after['observation_id']=2
        literal='SECOND-DOCUMENT-TAIL';actual=next(c for c in candidates_for(before,[literal]) if c['id']=='edit-p0')
        history=[{'operation':actual,'observed_source_identity':public_source_identity(before,actual['target']),
                  'receipt':{'accepted':True,'effect':'confirmed','readback':{'text':literal}},
                  'client_public_text_comparison':public_text_comparison(before,after)}]
        class Evidence:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                e=state['latest_execution_evidence']
                self_ref=e['observed_source_identity']['locator_ref']
                assert self_ref=='fixture-address-10'
                assert e['historical_target_export_key']==10 and e['current_source_at_same_locator']==110
                assert e['current_value_at_same_locator_equals_parameter'] is True
                assert e['current_context_at_same_locator']['target']==110
                assert e['current_public_text_readback']['independent_task_completion']=='not_assessed'
                if 'final_decision' in questions:return reviewed('done')
                if 'proposal' in questions:return proposal('done')
                return evaluation(goal_status='achieved')
        bridge=Mock(snapshot=Mock(return_value=after))
        answer=choose_iterative(Evidence(),'The current public text goal',after,candidates_for(after,[literal]),history)
        self.assertEqual(answer['choice'],'done');bridge.execute.assert_not_called()

    def test_public_field_prefix_retains_duplicate_targets_and_nonnumeric_member_order(self):
        doc=small_document();template=doc['operations'][0]
        doc['operations']=[{**template,'id':f'runtime-{(i*73)%1009}',
                            'label':'Execute' if i==299 else ('Remove' if i%2==0 else 'Keep'),
                            'target':4 if i%4==0 else 5} for i in range(300)]
        for wanted in (doc['operations'][298],doc['operations'][299]):
            events=[];calls=[]
            class Decoder:
                model='stub';metadata={}
                def decide(self,*,state,questions):
                    calls.append(questions)
                    if 'kind' in questions:
                        assert [r[0] for r in state['candidate_catalog']['rows']]==[o['id'] for o in doc['operations']]
                        return {'kind':{'type':'choice','choice':'kind/action'}}
                    if 'public_fields' in questions:
                        groups={k:json.loads(v) for k,v in questions['public_fields']['criteria'].items() if k!='abstain'}
                        assert sum(g['candidate_count'] for g in groups.values())==300
                        selected=next(k for k,g in groups.items() if g['public_fields']=={'name':wanted['name'],'label':wanted['label']})
                        return {'public_fields':{'type':'choice','choice':selected}}
                    if 'branch' in questions:
                        fields=state['conditional_on']['public_fields']
                        ids=[o['id'] for o in doc['operations'] if {k:o[k] for k in ('name','label')}==fields]
                        selected=next(k for k,v in questions['branch']['criteria'].items() if k!='abstain'
                                      and ids.index(json.loads(v)['first_candidate'])<=ids.index(wanted['id'])<=ids.index(json.loads(v)['last_candidate']))
                        return {'branch':{'type':'choice','choice':selected}}
                    if 'proposal' in questions:
                        assert wanted['id'] in questions['proposal']['criteria']
                        return proposal(wanted['id'])
                    if 'final_decision' in questions:return reviewed('act')
                    return evaluation()
            answer=choose_iterative(Decoder(),'Public operation',doc,candidates_for(doc),[],emit=events.append)
            self.assertEqual(answer['choice'],wanted['id'])
            if wanted['label']=='Execute':self.assertFalse(any('proposal' in q or 'branch' in q for q in calls))
            source=next(e for e in events if e['kind']=='iterative_source')
            roots=[e for e in events if e['kind']=='iterative_request' and e['stage']=='propose']
            self.assertEqual([r for e in roots for r in unpack(e['state']['current_records'])],RecordStore(source['source'],8192).records)

    def test_actual_execution_readback_reaches_proposal_and_evaluation_with_scope_guard(self):
        before=document();after=copy.deepcopy(before);after['observation_id']=before['observation_id']+1
        literal='SECOND-DOCUMENT-TAIL';candidates=candidates_for(after,[literal])
        actual=next(c for c in candidates if c['id']=='edit-p0')
        comparison=public_text_comparison(before,after)
        for scoped in (True,False):
            history=[{'operation':actual,'receipt':{'accepted':True,'effect':'confirmed','readback':{'text':literal}},
                      'client_public_text_comparison':copy.deepcopy(comparison)}]
            if not scoped:history[0]['client_public_text_comparison']['generation']='stale'
            class Evidence:
                model='stub';metadata={}
                def decide(self,*,state,questions):
                    evidence=state['latest_execution_evidence']
                    assert evidence['historical_target_export_key']==actual['target']
                    assert evidence['requested_parameter']==literal
                    assert evidence['receipt_text_equals_requested_parameter'] is True
                    if scoped:
                        assert evidence['current_value_at_matching_export_key_equals_parameter'] is True
                        assert evidence['current_context_at_historical_export_key']['target']==actual['target']
                        assert evidence['current_public_text_readback']['is_task_completion'] is False
                    else:
                        assert 'current_public_text_readback' not in evidence
                        assert 'current_context_at_historical_export_key' not in evidence
                    if 'final_decision' in questions:return reviewed('done' if scoped else 'abstain')
                    if 'proposal' in questions:return proposal('done')
                    return evaluation(goal_status='achieved' if scoped else 'pending')
            answer=choose_iterative(Evidence(),'Exact public text goal',after,candidates,history)
            self.assertEqual(answer['choice'],'done' if scoped else 'abstain')

    def test_actual_http_286_all_chunks_result_only_carry_and_one_operation(self):
        doc=document();op=doc['operations'][0]
        doc['operations']=[{**copy.deepcopy(op),'id':f'op-{i}','public_detail':'公开操作定义 '*20} for i in range(284)]+[doc['operations'][-2]]
        before=copy.deepcopy(doc);candidates=candidates_for(doc,['literal A','literal B'])
        self.assertEqual(len(candidates),286)
        with self.assertRaises(ChunkError) as caught:
            choose_chunked(Mock(model='stub'),'Read and edit',doc,candidates,[])
        self.assertEqual(caught.exception.kind,'final_base_overflow')
        bridge=Mock(snapshot=Mock(side_effect=[doc,document(2)]),execute=Mock(return_value={'accepted':True,'effect':'confirmed'}))
        previous=None;current=None;proposed=None;rounds=0
        def decide(payload):
            nonlocal previous,current,proposed,rounds
            bridge.execute.assert_not_called()
            state=payload['state']
            if 'final_decision' in payload['questions']:
                self.assertEqual(state['prior_model_result'],previous)
                self.assertTrue(state['source_scan_complete'])
                return reviewed('act')
            self.assertEqual(state['previous_result'],previous)
            self.assertNotIn('evidence',state);self.assertNotIn('history',state)
            self.assertNotIn('retained_record_ids',state)
            if any(k in payload['questions'] for k in ('kind','branch','proposal')):
                if 'candidate_catalog' in state:
                    catalog=state['candidate_catalog'];rows=catalog['rows']
                    self.assertEqual([r[0] for r in rows],[c['id'] for c in candidates])
                    for row,c in zip(rows,candidates):
                        ref=catalog['bindings'].get(c['id'],{'operation_ref':c['id']})
                        self.assertEqual(ref['operation_ref'],c['operation_id'])
                        if 'parameter' in c:self.assertEqual(ref['parameter'],c['parameter'])
                current=state['current_records']
                return routed_proposal('edit-p0' if rounds==0 else 'edit-p1',state,payload['questions'])
            self.assertEqual(state['current_records'],current)
            proposed=state['proposed_result']
            self.assertEqual(proposed['choice'],'edit-p0' if rounds==0 else 'edit-p1')
            self.assertEqual(state['proposed_operation']['operation'],doc['operations'][-1])
            expected=next(c for c in candidates if c['id']==proposed['choice'])
            self.assertEqual(state['proposed_target_context']['target_ancestors'],expected['target_ancestors'])
            answer=evaluation()
            rounds+=1
            return answer
        events=[]
        def emit(event):
            nonlocal previous
            events.append(event)
            if event['kind']=='iterative_progress':previous=copy.deepcopy(event['result'])
        with Stub(decide) as stub:
            result=run('Read and edit',bridge,stub.client,texts=['literal A','literal B'],max_steps=1,decision_mode='iterative-chunks',emit=emit)
        self.assertEqual(result['status'],'step_limit');bridge.execute.assert_called_once()
        self.assertEqual(bridge.execute.call_args.args[1]['parameter'],'literal B')
        source=next(e for e in events if e['kind']=='iterative_source')
        store=RecordStore(source['source'],8192)
        proposals=[p for p in stub.requests if 'kind' in p['questions']]
        self.assertEqual([r for p in proposals for r in unpack(p['state']['current_records'])],store.records)
        self.assertEqual(len(proposals),rounds);self.assertGreater(rounds,1)
        self.assertTrue(any(len(unpack(p['state']['current_records']))>24 for p in proposals))
        self.assertTrue(all(len(raw)<=60000 for raw in stub.raw))
        self.assertTrue(all(len(q.get('criteria',{}))<=255 for p in stub.requests for q in p['questions'].values()))
        self.assertEqual(sum(e['kind']=='iterative_release' for e in events),1)
        self.assertEqual(doc,before)

    def test_conditional_prefix_never_stitches_independent_digits_or_repairs_unknown_id(self):
        doc=document();template=doc['operations'][0]
        doc['operations']=[{**template,'id':f'op-{i}'} for i in range(810)]
        class Last:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'final_decision' in questions:return reviewed('act')
                if 'kind' in questions:return {'kind':{'type':'choice','choice':'kind/action'}}
                if 'branch' in questions:
                    catalog=state['candidate_catalog']
                    ids=[r[0] for r in catalog['rows'] if catalog['symbols']['kind'][r[1]]=='action']
                    restored=[]
                    for key,value in questions['branch']['criteria'].items():
                        if key=='abstain':continue
                        span=json.loads(value)
                        members=ids[ids.index(span['first_candidate']):ids.index(span['last_candidate'])+1]
                        assert len(members)==span['candidate_count']
                        restored.extend(members)
                    assert restored==ids
                    key=[k for k in questions['branch']['criteria'] if k!='abstain'][-1]
                    return {'branch':{'type':'choice','choice':key}}
                if 'proposal' in questions:
                    key=[k for k in questions['proposal']['criteria'] if k!='abstain'][-1]
                    return proposal(key)
                return evaluation()
        answer=choose_iterative(Last(),'Read',doc,candidates_for(doc),[])
        self.assertEqual(answer['choice'],'op-809')
        class Invalid:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'kind' in questions:return {'kind':{'type':'choice','choice':'kind/action'}}
                return {'branch':{'type':'choice','choice':'1019'}}
        bridge=Mock(snapshot=Mock(return_value=doc))
        result=run('Read',bridge,Invalid(),decision_mode='iterative-chunks')
        self.assertEqual(result['decision_error_kind'],'invalid_choice')
        bridge.execute.assert_not_called()

    def test_early_done_is_tentative_last_block_can_choose_any_other_candidate(self):
        doc=small_document();doc['future_public_text']='公开长正文'*10000
        events=[]
        class Fake:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'final_decision' in questions:return reviewed('act')
                if 'proposal' in questions:
                    return proposal('op-1' if state['progress']['all_records_evaluated_if_this_round_succeeds'] else 'done')
                return evaluation()
        answer=choose_iterative(Fake(),'Report B',doc,candidates_for(doc),[],emit=events.append)
        self.assertEqual(answer['choice'],'op-1')
        progress=[e for e in events if e['kind']=='iterative_progress']
        self.assertGreater(len(progress),1)
        self.assertEqual(progress[0]['result']['proposal']['choice'],'done')
        self.assertEqual(progress[-1]['result']['proposal']['choice'],'op-1')
        self.assertTrue(next(e for e in events if e['kind']=='iterative_release')['all_source_records_evaluated'])

    def test_negative_evaluation_abstains_and_malformed_or_failed_evaluation_never_dispatches(self):
        for bad in ('insufficient','unsupported_done','bad_probability','missing_answer','provider_error'):
            bridge=Mock(snapshot=Mock(return_value=small_document()))
            class Bad:
                model='stub';metadata={}
                def decide(self,*,state,questions):
                    if 'final_decision' in questions:return reviewed('abstain')
                    if 'proposal' in questions:return proposal('done' if bad=='unsupported_done' else 'op-0')
                    if bad=='bad_probability':return evaluation(support=True)
                    if bad=='missing_answer':return {'verdict':{'type':'choice','choice':'supported'}}
                    if bad=='provider_error':raise JevError('evaluator unavailable')
                    return evaluation() if bad=='unsupported_done' else evaluation('insufficient')
            result=run('Remove',bridge,Bad(),decision_mode='iterative-chunks')
            self.assertEqual(result['status'],'abstained' if bad in ('insufficient','unsupported_done') else 'failed')
            self.assertIsNone(result['task_completed']);bridge.execute.assert_not_called()

    def test_not_attempted_restarts_result_chain_unknown_not_replayed(self):
        events=[]
        class Fake:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'final_decision' in questions:return reviewed('act')
                return proposal('op-0') if 'proposal' in questions else evaluation()
        bridge=Mock(snapshot=Mock(side_effect=[small_document(1),small_document(2),small_document(3)]),
                    execute=Mock(side_effect=[NativeBridgeError({'delivery':'not_attempted','error':'stale'}),{'accepted':True,'effect':'unknown'}]))
        result=run('Remove',bridge,Fake(),decision_mode='iterative-chunks',emit=events.append)
        self.assertEqual(result['status'],'unknown');self.assertEqual(bridge.execute.call_count,2)
        sources=[e for e in events if e['kind']=='iterative_source'];self.assertEqual(len(sources),2)
        self.assertNotEqual(sources[0]['source_sha256'],sources[1]['source_sha256'])
        self.assertEqual(sources[1]['source']['history'][0]['receipt']['delivery'],'not_attempted')
        for source in sources:
            requests=[e for e in events if e['kind']=='iterative_request' and e['source_sha256']==source['source_sha256']]
            self.assertIsNone(requests[0]['state']['previous_result'])
            progress=[e for e in events if e['kind']=='iterative_progress' and e['source_sha256']==source['source_sha256']]
            self.assertEqual(sum(len(e['evaluated_record_ids']) for e in progress),source['record_count'])

    def test_large_previous_result_and_large_operation_fail_without_clipping(self):
        for large in ('result','definition'):
            doc=small_document();events=[]
            doc['future_public_text']='公开材料'*40000
            if large=='definition':doc['operations'][0]['future_public_detail']='完整定义'*20000
            class Big:
                model='stub';metadata={}
                def decide(self,*,state,questions):
                    if 'proposal' in questions:return proposal('op-0')
                    answer=evaluation()
                    if large=='result':answer['assessment']['future_model_field']='完整模型输出'*20000
                    return answer
            bridge=Mock(snapshot=Mock(return_value=doc))
            result=run('Read',bridge,Big(),decision_mode='iterative-chunks',chunk_options=ChunkOptions(max_questions=1),emit=events.append)
            self.assertEqual(result['decision_error_kind'],'reader_base_overflow' if large=='result' else 'request_overflow')
            bridge.execute.assert_not_called()
            if large=='result':
                progress=next(e for e in events if e['kind']=='iterative_progress')
                self.assertEqual(progress['result']['evaluation']['assessment']['future_model_field'],'完整模型输出'*20000)

    def test_model_done_after_complete_scan_is_not_independent_task_completion(self):
        class Done:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'final_decision' in questions:return reviewed('done')
                return proposal('done') if 'proposal' in questions else evaluation(goal_status='achieved')
        bridge=Mock(snapshot=Mock(return_value=small_document()))
        result=run('Read',bridge,Done(),decision_mode='iterative-chunks')
        self.assertEqual(result['status'],'model_completed');self.assertIsNone(result['task_completed'])
        bridge.execute.assert_not_called()

    def test_complete_public_parameter_comparison_informs_model_done_without_repeating_write(self):
        literal='SECOND-DOCUMENT-TAIL'
        for complete in (True,False):
            doc=document();doc['text_payloads'][1]['read']['status']='complete' if complete else 'unavailable'
            class Compare:
                model='stub';metadata={}
                def decide(self,*,state,questions):
                    assert state['input_parameters']==[literal]
                    if 'final_decision' in questions:
                        assert state['source_scan_complete']
                        assert state['prior_model_result']['effective_assessment']['choice']==('supported' if complete else 'insufficient')
                        return reviewed('done' if complete else 'abstain')
                    if 'proposal' in questions:return proposal('edit-p0')
                    if not state['progress']['all_records_evaluated_if_this_round_succeeds']:return evaluation()
                    check=state['public_parameter_checks'][0]
                    if complete:
                        assert check['parameter_equals_current_public_text'] is True
                        return evaluation()
                    assert check['parameter_comparison']=='unavailable'
                    assert 'parameter_equals_current_public_text' not in check
                    return evaluation(verdict='insufficient')
            bridge=Mock(snapshot=Mock(return_value=doc))
            result=run('Finish exact text',bridge,Compare(),texts=[literal],decision_mode='iterative-chunks')
            self.assertEqual(result['status'],'model_completed' if complete else 'abstained')
            self.assertIsNone(result['task_completed']);bridge.execute.assert_not_called()

    def test_model_explicit_keep_preserves_binding_and_new_contradiction_revokes_it(self):
        doc=small_document();doc['future_public_text']='BODY-DONT-CARRY-'*10000
        events=[];rounds=0
        class Keep:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                nonlocal rounds
                previous=state.get('previous_result')
                if previous is not None:
                    assert 'BODY-DONT-CARRY-' not in json.dumps(previous)
                if 'final_decision' in questions:
                    assert state['prior_model_result']['binding'] is None
                    assert state['prior_model_result']['effective_assessment']['choice']=='contradicted'
                    return reviewed('act')
                if 'proposal' in questions:return proposal('op-0')
                if rounds==0:
                    assert 'keep_previous' not in questions['assessment']['criteria']
                    answer=evaluation()
                else:
                    binding=previous['binding'];assert binding['candidate_id']=='op-0'
                    assert binding['observation_id']==doc['observation_id']
                    assert binding['is_execution_authority'] is False
                    answer=evaluation('contradicted' if state['progress']['all_records_evaluated_if_this_round_succeeds'] else 'keep_previous')
                rounds+=1;return answer
        bridge=Mock(snapshot=Mock(return_value=doc))
        result=run('Remove',bridge,Keep(),decision_mode='iterative-chunks',emit=events.append)
        self.assertEqual(result['status'],'abstained');bridge.execute.assert_not_called()
        progress=[e for e in events if e['kind']=='iterative_progress']
        self.assertGreater(len(progress),2)
        self.assertEqual(progress[0]['result']['binding'],progress[1]['result']['binding'])
        self.assertIsNone(progress[-1]['result']['binding'])

    def test_keep_proposal_is_explicit_model_choice_with_full_root_open(self):
        doc=document();template=doc['operations'][0]
        doc['operations']=[{**template,'id':f'op-{i}'} for i in range(810)]
        doc['future_public_text']=''.join(f'{i}:public-detail;' for i in range(20000))
        events=[]
        class Kept:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                if 'final_decision' in questions:return reviewed('act')
                if 'kind' in questions:
                    assert len(state['candidate_catalog']['rows'])==810
                    assert 'kind/action' in questions['kind']['criteria']
                    return {'kind':{'type':'choice','choice':'keep_proposal' if 'keep_proposal' in questions['kind']['criteria'] else 'kind/action'}}
                if 'branch' in questions:
                    return {'branch':{'type':'choice','choice':[k for k in questions['branch']['criteria'] if k!='abstain'][-1]}}
                if 'proposal' in questions:return proposal('op-809')
                return evaluation('keep_previous' if 'keep_previous' in questions['assessment']['criteria'] else 'supported')
        answer=choose_iterative(Kept(),'Read',doc,candidates_for(doc),[],emit=events.append)
        self.assertEqual(answer['choice'],'op-809')
        requests=[e for e in events if e['kind']=='iterative_request']
        self.assertEqual(sum(e['stage']=='propose_member' for e in requests),1)
        self.assertGreater(sum(e['stage']=='propose' for e in requests),1)
        self.assertEqual(sum(e['stage']=='propose_branch' for e in requests),1)

    def test_complete_assessment_can_be_kept_when_proposal_changes_to_done(self):
        doc=small_document();doc['future_public_text']=''.join(f'{i}:remaining public data;' for i in range(15000))
        first=True
        class Complete:
            model='stub';metadata={}
            def decide(self,*,state,questions):
                nonlocal first
                if 'final_decision' in questions:
                    assert state['prior_model_result']['effective_assessment']['choice']=='complete'
                    assert state['prior_model_result']['proposal']['choice']=='done'
                    return reviewed('done')
                if 'proposal' in questions:return proposal('op-0' if first else 'done')
                if first:first=False;return evaluation(goal_status='achieved')
                assert 'keep_complete' in questions['assessment']['criteria']
                return evaluation('keep_complete')
        bridge=Mock(snapshot=Mock(return_value=doc))
        result=run('Read',bridge,Complete(),decision_mode='iterative-chunks')
        self.assertEqual(result['status'],'model_completed');self.assertIsNone(result['task_completed'])
        bridge.execute.assert_not_called()


if __name__=='__main__':unittest.main()
