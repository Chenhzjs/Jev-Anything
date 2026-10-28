import copy
import unittest
from unittest.mock import patch

from test_tui import frame, Bridge
from jev_anything.workflow import VERSION, run_workflow, validate_workflow
from jev_anything.workflow_recording import RecordingSession, confirm_recording, confirmed_recipe, digest


def recipe(two=False):
    step = {'name': 'first', 'locate': {'action': 'find_action', 'query': 'Public control'},
            'operation': {'kind': 'action', 'name': 'Press'},
            'after': {'kind': 'control', 'locate': {'action': 'find_action', 'query': 'Next phase'}}}
    steps = [step]
    if two: steps.append({**copy.deepcopy(step), 'name': 'second'})
    return {'version': VERSION, 'name': 'public task', 'goal': 'Reach declared public checkpoints',
            'steps': steps, 'endpoint': {'kind': 'pause', 'reason': 'User boundary; no automatic continuation'}}


class WorkflowBridge(Bridge):
    def __init__(self, *, ambiguous=False, absent=False, remap=False, rejected=None):
        super().__init__([], rejected=rejected); self.serial=0
        self.ambiguous=ambiguous; self.absent=absent; self.remap=remap

    def request(self, command, **kwargs):
        self.requests.append((command, kwargs)); self.serial+=1
        value=frame(self.serial, remap=self.remap and self.serial>3, operation=f'workflow-op-{self.serial}')
        value['observation']['operations'][0].update(kind='action', name='Press')
        value['navigation'].update(status='focused', selection_confirmed=True,
                                   target=111 if self.remap and self.serial>3 else 11)
        if command=='tui_navigate':
            if self.ambiguous: value['navigation'].update(status='ambiguous', selection_confirmed=False)
            if self.absent and kwargs['query']=='Next phase':value['navigation'].update(status='not_found', selection_confirmed=False)
        return value


class WorkflowTests(unittest.TestCase):
    def test_live_ids_are_resolved_each_run_without_provider_and_checkpoint_is_not_task_success(self):
        with patch('jev_anything.tui.DeepSeekClient', side_effect=AssertionError('Provider must not be used')):
            for _ in range(2):
                b=WorkflowBridge(); result=run_workflow(recipe(), b, poll_seconds=0)
                self.assertEqual(result['status'], 'pause'); self.assertIsNone(result['task_completed'])
                self.assertEqual(result['provider_calls'], 0); self.assertEqual(result['input_tokens'], 0)
                self.assertEqual(result['completed_steps'], ['first'])
                self.assertEqual(b.executions[0][0], 2)
                self.assertEqual(b.executions[0][1]['operation_id'], 'workflow-op-2')

    def test_ambiguity_and_missing_postcondition_stop_without_fallback_or_write_replay(self):
        b=WorkflowBridge(ambiguous=True); result=run_workflow(recipe(), b, poll_seconds=0)
        self.assertEqual(result['status'], 'blocked'); self.assertEqual(b.executions, [])
        b=WorkflowBridge(absent=True);result=run_workflow(recipe(two=True), b, max_observations=2, poll_seconds=0)
        self.assertEqual(result['status'], 'blocked');self.assertEqual(len(b.executions), 1)
        self.assertEqual(result['completed_steps'], [])

    def test_not_attempted_reobserves_but_does_not_retry_and_delivery_unknown_stops(self):
        for delivery in ['not_attempted','unknown']:
            b=WorkflowBridge(rejected={'ok':False, 'delivery':delivery, 'error':'Rejected by G2T'})
            result=run_workflow(recipe(), b, poll_seconds=0)
            self.assertEqual(result['status'], 'blocked' if delivery=='not_attempted' else 'unknown')
            self.assertEqual(len(b.executions), 1)
            if delivery=='not_attempted':self.assertEqual(b.requests[-1][0], 'observe_tui_text')

    def test_unknown_operation_cannot_reappear_under_renumbered_ids(self):
        b=WorkflowBridge(remap=True);b.receipt={'accepted':True,'effect':'unknown'}
        result=run_workflow(recipe(two=True), b, poll_seconds=0)
        self.assertEqual(result['status'], 'blocked'); self.assertIn('not replayed', result['reason'])
        self.assertEqual(len(b.executions), 1)

    def test_recipe_cannot_supply_cached_ids_hidden_actions_or_generated_write_text(self):
        for key,value in [('operation_id','old-op'), ('parameter','guessed text')]:
            bad=recipe();bad['steps'][0][key]=value
            with self.assertRaises(ValueError):validate_workflow(bad)
        bad=recipe();bad['steps'][0]['operation']={'kind':'action'}
        with self.assertRaises(ValueError):validate_workflow(bad)
        bad=recipe();bad['steps'][0]['operation']['name']='not public'
        b=WorkflowBridge();result=run_workflow(bad,b,poll_seconds=0)
        self.assertEqual(result['status'],'blocked');self.assertEqual(b.executions,[])
        bad=recipe();bad['steps'][0]['literal_index']=0
        b=WorkflowBridge();result=run_workflow(bad,b,poll_seconds=0)
        self.assertEqual(result['status'],'blocked');self.assertEqual(b.requests,[])

    def test_actual_recording_must_be_confirmed_and_edits_require_new_confirmation(self):
        r=recipe();session=RecordingSession(WorkflowBridge(),name=r['name'],goal=r['goal'],actor='human')
        session.record_step(r['steps'][0],poll_seconds=0)
        draft=session.draft(r['endpoint'])
        with self.assertRaises(ValueError):confirmed_recipe(draft)
        approved=confirm_recording(draft,expected_digest=digest(draft),confirmed_by='human')
        self.assertEqual(confirmed_recipe(approved),r)
        approved['recipe']['steps'][0]['locate']['query']='changed'
        with self.assertRaises(ValueError):confirmed_recipe(approved)
        with self.assertRaises(ValueError):confirm_recording(draft,expected_digest='wrong',confirmed_by='agent')

    def test_recording_failure_and_unknown_cannot_be_promoted_or_replayed_across_steps(self):
        r=recipe();b=WorkflowBridge();b.receipt={'accepted':True,'effect':'unknown'}
        session=RecordingSession(b,name=r['name'],goal=r['goal'],actor='agent')
        self.assertEqual(session.record_step(r['steps'][0],poll_seconds=0)['status'],'checkpoints_reached')
        result=session.record_step(r['steps'][0],poll_seconds=0)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(b.executions),1)
        with self.assertRaises(RuntimeError):session.draft(r['endpoint'])


if __name__=='__main__':unittest.main()
