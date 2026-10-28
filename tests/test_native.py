import copy
import unittest
from unittest.mock import Mock, patch
from jev_anything.jev import JevConfig
from jev_anything.native import NativeBridgeError, candidates_for, choose, run
from test_document import identity_document, remap_snapshot_ids
from test_chunked import small_document
from jev_anything.document import SOURCE_IDENTITY_VERSION


def snapshot(serial=1):
    return dict(session='session-1', generation=1, observation_id=serial, partial=False, interaction_scope='window-1', nodes=[],
                operations=[dict(id='op-1', target=1, kind='action', label='Save'),
                            dict(id='op-2', target=2, kind='replace_text', label='Query', parameter='text')])


class NativeTests(unittest.TestCase):
    def test_no_write_selection_result_observes_again_and_requires_a_fresh_decision(self):
        before=small_document();before['operations']=[dict(id='clear',target=4,kind='selection',selected=False,agent_invocable=True)]
        after=copy.deepcopy(before);after['observation_id']=2
        receipt={'accepted':None,'effect':'already_satisfied','delivery':'not_attempted',
            'operation_id':'clear','observation_id':before['observation_id'],
            'readback':{'selection_outcome_version':'gui2tui.selection-outcome.v1',
                        'selected':False,'already_satisfied':True,'write_invoked':False}}
        bridge=Mock(snapshot=Mock(side_effect=[before,after]),execute=Mock(return_value=receipt))
        provider=Mock(model='stub',metadata={},decide=Mock(side_effect=[
            {'action':{'type':'choice','choice':'clear'}},{'action':{'type':'choice','choice':'abstain'}}]))
        result=run('A GUI goal',bridge,provider,max_steps=2)
        self.assertEqual(result['status'],'abstained')
        self.assertIsNone(result['task_completed'])
        self.assertEqual(provider.decide.call_args_list[1].kwargs['state']['accessibility']['observation_id'],2)
        self.assertEqual(result['history'][0]['receipt']['accepted'],None)
        bridge.execute.assert_called_once();self.assertEqual(bridge.snapshot.call_count,2)

    def test_malformed_no_write_result_never_bypasses_unknown_stop(self):
        before=small_document();before['operations']=[dict(id='clear',target=4,kind='selection',selected=False,agent_invocable=True)]
        for wrong in ('write_invoked','selected','observation_id'):
            receipt={'accepted':None,'effect':'already_satisfied','delivery':'not_attempted',
                'operation_id':'clear','observation_id':before['observation_id'],
                'readback':{'selection_outcome_version':'gui2tui.selection-outcome.v1',
                            'selected':False,'already_satisfied':True,'write_invoked':False}}
            if wrong=='observation_id':receipt[wrong]=-1
            else:receipt['readback'][wrong]=True
            bridge=Mock(snapshot=Mock(return_value=before),execute=Mock(return_value=receipt))
            provider=Mock(model='stub',metadata={},decide=Mock(return_value={'action':{'type':'choice','choice':'clear'}}))
            result=run('A GUI goal',bridge,provider,max_steps=2)
            self.assertEqual(result['status'],'unknown');bridge.execute.assert_called_once()
            self.assertIn('Malformed already-satisfied',result['error'])

    def test_unknown_source_reference_blocks_renumbered_replay_and_keeps_original_guard(self):
        for renumber in (True,False):
            before=small_document();before['source_identity']={'version':SOURCE_IDENTITY_VERSION,
                'namespace':{k:before[k] for k in ('session','generation')}}
            for n in before['nodes']:n['locator_ref']=f'public-address-{n["id"]}'
            after=remap_snapshot_ids(before) if renumber else copy.deepcopy(before)
            after['observation_id']=2
            if not renumber:next(n for n in after['nodes'] if n['id']==4)['locator_ref']='changed-address'
            bridge=Mock(snapshot=Mock(side_effect=[before,after]),
                        execute=Mock(return_value={'accepted':True,'effect':'unknown'}))
            provider=Mock(model='stub',metadata={},decide=Mock(side_effect=[
                {'action':{'type':'choice','choice':'op-0'}},
                {'action':{'type':'choice','choice':'op-0'}}]))
            result=run('Use the public operation',bridge,provider,max_steps=2)
            self.assertEqual(result['status'],'unknown')
            self.assertIn('not replayed',result['reason'])
            bridge.execute.assert_called_once()
            self.assertEqual(provider.decide.call_count,2)

    def test_miyang_key_without_printing_it(self):
        with patch.dict('os.environ', {'MIYANG_API_KEY': 'test-only'}, clear=True):
            self.assertEqual(JevConfig.from_env().api_key, 'test-only')

    def test_parameters_are_explicit_user_data(self):
        self.assertEqual(len(candidates_for(snapshot())), 1)
        options = candidates_for(snapshot(), ['nebula'])
        self.assertEqual(options[1]['operation_id'], 'op-2')
        self.assertEqual(options[1]['parameter'], 'nebula')

    def test_unknown_model_id_never_executes(self):
        bridge = Mock(snapshot=Mock(return_value=snapshot()))
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={'action': {'type': 'choice', 'choice': 'invented'}}))
        result = run('Save', bridge, provider)
        self.assertEqual(result['status'], 'failed')
        bridge.execute.assert_not_called()

    def test_non_string_choice_is_rejected_without_dispatch(self):
        for choice in ([], {}, ['op-1'], {'id': 'op-1'}, 1, True, None):
            with self.subTest(choice=choice):
                bridge = Mock(snapshot=Mock(return_value=snapshot()))
                provider = Mock(model='test', metadata={}, decide=Mock(return_value={
                    'action': {'type': 'choice', 'choice': choice}}))
                events = []
                result = run('Save', bridge, provider, emit=events.append)
                self.assertEqual(result['status'], 'failed')
                self.assertIn('Invalid or unknown choice', result['error'])
                self.assertIsNone(result['task_completed'])
                bridge.execute.assert_not_called()
                self.assertEqual(provider.decide.call_count, 1)
                self.assertEqual(sum(e['kind'] == 'decision_timing' for e in events), 1)

    def test_unknown_unchanged_delivery_stops_without_retry(self):
        bridge = Mock(snapshot=Mock(side_effect=[snapshot(1), snapshot(2)]),
                      execute=Mock(return_value={'accepted': True, 'effect': 'unknown'}))
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={'action': {'type': 'choice', 'choice': 'op-1'}}))
        result = run('Save', bridge, provider)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(bridge.execute.call_count, 1)

    def test_model_done_is_not_task_confirmation(self):
        bridge = Mock(snapshot=Mock(return_value=snapshot()))
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={'action': {'type': 'choice', 'choice': 'done'}}))
        result = run('Save', bridge, provider)
        self.assertEqual(result['status'], 'model_completed')
        self.assertIsNone(result['task_completed'])
        bridge.execute.assert_not_called()

    def test_proven_not_dispatched_allows_a_fresh_decision(self):
        bridge = Mock(snapshot=Mock(side_effect=[snapshot(1), snapshot(2)]),
                      execute=Mock(side_effect=NativeBridgeError({'delivery': 'not_attempted', 'error': 'stale target'})))
        provider = Mock(model='test', metadata={}, decide=Mock(side_effect=[
            {'action': {'type': 'choice', 'choice': 'op-1'}},
            {'action': {'type': 'choice', 'choice': 'done'}}]))
        result = run('Save', bridge, provider)
        self.assertEqual(result['status'], 'model_completed')
        self.assertEqual(provider.decide.call_count, 2)
        self.assertEqual(bridge.execute.call_count, 1)

    def test_unknown_dispatch_observes_consequence_without_replay(self):
        bridge = Mock(snapshot=Mock(side_effect=[snapshot(1), snapshot(2)]),
                      execute=Mock(side_effect=NativeBridgeError({
                          'delivery': 'unknown', 'error': 'Text readback differs'})))
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={
            'action': {'type': 'choice', 'choice': 'op-1'}}))
        events = []
        result = run('Save', bridge, provider, emit=events.append)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['observation']['observation_id'], 2)
        self.assertIsNone(result['task_completed'])
        self.assertEqual(bridge.execute.call_count, 1)
        self.assertEqual(provider.decide.call_count, 1)
        self.assertEqual(bridge.snapshot.call_count, 2)
        self.assertEqual(sum(e['kind'] == 'delivery_unknown' for e in events), 1)
        self.assertEqual(sum(e['kind'] == 'readback' for e in events), 1)

class ContextTests(unittest.TestCase):
    def test_candidate_target_and_ancestors_are_structured(self):
        observation = snapshot()
        observation['nodes'] = [
            {'id': 1, 'parent': None, 'role': 'Window', 'label': 'Main', 'value': '', 'states': ['visible'], 'redacted': False},
            {'id': 2, 'parent': 1, 'role': 'Button', 'label': 'Save', 'value': '', 'states': ['visible', 'enabled'], 'redacted': False},
        ]
        observation['operations'][0]['target'] = 2
        from jev_anything.native import context_for
        candidate = candidates_for(observation)[0]
        self.assertEqual(candidate['target_state'], 'available')
        self.assertEqual(candidate['target_role'], 'Button')
        self.assertEqual(candidate['target_ancestors'][0]['id'], 1)
        context = context_for(observation, [candidate])
        self.assertIn(2, context['required_node_ids'])

    def test_full_context_keeps_all_public_nodes(self):
        observation = snapshot()
        observation['nodes'] = [
            {'id': i, 'parent': None, 'role': 'Text', 'label': 'x' * 500, 'value': '', 'states': ['visible'], 'redacted': False}
            for i in range(1, 200)
        ]
        observation['operations'] = [{'id': 'save', 'target': 1, 'kind': 'action', 'name': 'save', 'label': 'Save'}]
        from jev_anything.native import context_for
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={'action': {'type': 'choice', 'choice': 'abstain'}}))
        choose(provider, 'Save', observation, candidates_for(observation), [])
        state = provider.decide.call_args.kwargs['state']
        self.assertIn(1, state['accessibility']['required_node_ids'])
        self.assertEqual(len(state['accessibility']['nodes']), len(observation['nodes']))

    def test_public_evidence_and_operation_semantics_reach_provider(self):
        observation = snapshot()
        observation['nodes'] = [
            dict(id=1, parent=None, role='Slider', label='Volume', value='30',
                 states=['Enabled'], description='Adjust listening volume', partial=True,
                 region='controls', redacted=False),
            dict(id=2, parent=None, role='Password', label=None, value=None,
                 states=[], redacted=True),
        ]
        observation['operations'] = [
            dict(id='increase', target=1, kind='adjust_value', increase=True),
            dict(id='remove', target=1, kind='selection', selected=False),
            dict(id='edit', target=1, kind='replace_text', multiline=True, parameter='text'),
        ]
        provider = Mock(model='test', metadata={}, decide=Mock(return_value={
            'action': {'type': 'choice', 'choice': 'abstain'}}))
        choose(provider, 'Adjust', observation, candidates_for(observation, ['literal']), [])
        request = provider.decide.call_args.kwargs
        context = request['state']['accessibility']
        self.assertEqual(context['nodes'], observation['nodes'][:1])
        self.assertTrue(context['partial'])
        self.assertEqual(context['observation_id'], observation['observation_id'])
        import json
        criteria = request['questions']['action']['criteria']
        self.assertIs(json.loads(criteria['increase'])['increase'], True)
        self.assertIs(json.loads(criteria['remove'])['selected'], False)
        self.assertIs(json.loads(criteria['edit-p0'])['multiline'], True)
        self.assertEqual(json.loads(criteria['edit-p0'])['parameter'], 'literal')
        self.assertEqual(json.loads(criteria['increase'])['target_states'], ['Enabled'])

    def test_trace_preserves_provider_request_and_failure(self):
        from jev_anything.jev import JevError
        provider = Mock(model='test', metadata={'http_status': 413},
                        decide=Mock(side_effect=JevError('Request rejected')))
        events = []
        result = run('Save', Mock(snapshot=Mock(return_value=snapshot())),
                     provider, emit=events.append)
        self.assertEqual(result['status'], 'failed')
        request = next(e for e in events if e['kind'] == 'decision_request')
        self.assertEqual(request['state'], provider.decide.call_args.kwargs['state'])
        self.assertEqual(request['questions'], provider.decide.call_args.kwargs['questions'])
        error = next(e for e in events if e['kind'] == 'decision_error')
        self.assertEqual(error['usage']['http_status'], 413)

    def test_context_and_candidate_criteria_do_not_truncate_public_structure(self):
        observation = snapshot()
        parent = None
        nodes = []
        for i in range(1, 9):
            nodes.append({'id': i, 'parent': parent, 'role': 'Container',
                          'label': f'ancestor-{i}', 'value': '',
                          'states': ['visible'], 'redacted': False})
            parent = i
        long_label = 'x' * 1000
        nodes.append({'id': 9, 'parent': parent, 'role': 'Button',
                      'label': long_label, 'value': '',
                      'states': ['visible', 'enabled'], 'redacted': False})
        observation['nodes'] = nodes
        observation['operations'] = [{'id': 'deep', 'target': 9, 'kind': 'action',
                                      'name': 'activate', 'label': long_label}]
        from jev_anything.native import context_for, _candidate_view
        candidate = candidates_for(observation)[0]
        provider = Mock(model='test', metadata={}, decide=Mock(
            return_value={'action': {'type': 'choice', 'choice': 'abstain'}}))
        choose(provider, 'Finish', observation, [candidate], [])
        state = provider.decide.call_args.kwargs['state']
        self.assertEqual(len(state['accessibility']['nodes']), len(nodes))
        self.assertEqual(len(candidate['target_ancestors']), 8)
        self.assertEqual(_candidate_view(candidate)['label'], long_label)
        self.assertEqual(len(_candidate_view(candidate)['target_ancestors']), 8)

    def test_large_candidate_set_uses_one_complete_decision(self):
        observation = snapshot()
        observation['operations'] = [
            {'id': f'op-{i}', 'target': 1, 'kind': 'action', 'name': 'click', 'label': f'Click {i}'}
            for i in range(251)
        ]
        provider = Mock(model='test', metadata={}, decide=Mock(
            return_value={'action': {'type': 'choice', 'choice': 'done'}}))
        result = run('Finish the task', Mock(snapshot=Mock(return_value=observation)), provider)
        self.assertEqual(result['status'], 'model_completed')
        self.assertIsNone(result['task_completed'])
        self.assertEqual(provider.decide.call_count, 1)
