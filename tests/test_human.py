import copy
import io
import unittest
from unittest.mock import patch
from test_workflow import WorkflowBridge, recipe
from jev_anything.human import terminal_handler
from jev_anything.workflow import HUMAN_VERSION, run_workflow, validate_workflow
from jev_anything.workflow_recording import RecordingSession, confirm_recording, confirmed_recipe, digest
from jev_anything.human_view import start_viewer


def manual():
    r=recipe();r['version']=HUMAN_VERSION
    r['steps']=[{'kind':'human','name':'manual verification','instructions':'Use the original GUI, then return',
                 'after':{'kind':'control','locate':{'action':'find_action','query':'Next phase'}}}]
    return r


class HumanTests(unittest.TestCase):
    def test_handoff_cancel_missing_handler_and_ack_without_checkpoint_do_not_write_or_claim_success(self):
        for handler,status in [(None,'needs_human'),(lambda _: 'cancel','cancelled')]:
            b=WorkflowBridge();r=run_workflow(manual(),b,poll_seconds=0,human_handler=handler)
            self.assertEqual(r['status'],status);self.assertEqual(b.executions,[])
            self.assertEqual(r['completed_steps'],[]);self.assertIsNone(r['task_completed'])
        b=WorkflowBridge(absent=True);r=run_workflow(manual(),b,poll_seconds=0,max_observations=1,human_handler=lambda _: 'resume')
        self.assertEqual(r['status'],'blocked');self.assertEqual(b.executions,[])

    def test_resume_reobserves_and_uses_current_G2T_ids_and_generation_changes_stop(self):
        r=manual();r['steps']+=recipe()['steps']
        b=WorkflowBridge();result=run_workflow(r,b,poll_seconds=0,human_handler=lambda _: 'resume')
        self.assertEqual(result['status'],'pause');self.assertEqual(len(b.executions),1)
        self.assertGreater(b.executions[0][0],2)
        class Restart(WorkflowBridge):
            def request(self,command,**kwargs):
                value=super().request(command,**kwargs)
                if self.serial>1:
                    value['observation']['generation']={'new':'generation'};value['tui_view']['generation']={'new':'generation'}
                return value
        b=Restart();result=run_workflow(r,b,poll_seconds=0,human_handler=lambda _: 'resume')
        self.assertEqual(result['status'],'blocked');self.assertEqual(b.executions,[])

    def test_manual_recording_requires_new_version_and_real_ack_checkpoint_not_a_receipt(self):
        r=manual();bad=copy.deepcopy(r);bad['version']='jev.workflow.experimental.v1'
        with self.assertRaises(ValueError):validate_workflow(bad)
        bad=copy.deepcopy(r);bad['steps'][0]['after']={'kind':'readback'}
        with self.assertRaises(ValueError):validate_workflow(bad)
        recorder=RecordingSession(WorkflowBridge(),name=r['name'],goal=r['goal'],actor='human')
        result=recorder.record_step(r['steps'][0],human_handler=lambda _: 'resume',poll_seconds=0)
        self.assertEqual(result['status'],'checkpoints_reached')
        draft=recorder.draft(r['endpoint']);approved=confirm_recording(draft,expected_digest=digest(draft),confirmed_by='human')
        self.assertEqual(confirmed_recipe(approved)['version'],HUMAN_VERSION)
        self.assertFalse(any(e['kind']=='receipt' for e in result['history']))

    def test_terminal_only_records_fixed_decision_and_eof_cancels(self):
        output=io.StringIO();handler=terminal_handler(stream=io.StringIO('private transient input\nRESUME\n'),output=output)
        self.assertEqual(handler({'instructions':'Operate original GUI'}),'resume')
        self.assertNotIn('private transient input',output.getvalue())
        self.assertEqual(terminal_handler(stream=io.StringIO(''),output=io.StringIO())({'instructions':'Operate'}),'cancel')
        with self.assertRaises(ValueError):terminal_handler('javascript:alert(1)')

    def test_viewer_rejects_public_bindings_and_injected_container_display_before_start(self):
        with patch('jev_anything.human_view._run',return_value='[{"NetworkSettings":{"Ports":{"6080/tcp":[{"HostIp":"0.0.0.0","HostPort":"6083"}]}}}]') as run:
            with self.assertRaises(ValueError):start_viewer('demo',':490',user='501')
            self.assertEqual(run.call_count,1)
        for container,display in [('--privileged',':490'),('demo',':490; bad')]:
            with patch('jev_anything.human_view._run') as run:
                with self.assertRaises(ValueError):start_viewer(container,display,user='501')
                run.assert_not_called()


if __name__=='__main__':unittest.main()
