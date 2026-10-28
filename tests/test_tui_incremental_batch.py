import copy
import json
import unittest
from unittest.mock import Mock

from test_tui import frame,Bridge,Planner
from jev_anything.deepseek import DeepSeekConfig
from jev_anything.document import public_source_identity
from jev_anything.tui import TuiPlanner,Budget,decode_request_state,model_state,validate_plan,run_tui


def done():
    return {'kind':'done','evidence':[{'kind':'node_state','target':11,'state':'Enabled','present':True}]}


def two_fields(serial=1,after=False):
    f=frame(serial,operation='new-first' if after else 'op-0')
    doc=f['observation'];first=doc['operations'][0]
    first.update(kind='replace_text',parameter='text',parameter_domain={'kind':'text'})
    second=copy.deepcopy(doc['nodes'][-1]);second.update(id=12,locator_ref='fixture-address-12',label='Second field')
    doc['nodes'].append(second)
    op=copy.deepcopy(first);op.update(id='new-second' if after else 'op-second',target=12)
    doc['operations'].append(op)
    f['tui_view']['visible_bindings'].append({'target':12,'operations':[op]})
    return f


def batch():
    return {'kind':'batch','operations':[{'operation_id':'op-0','literal_index':0},
                                       {'operation_id':'op-second','literal_index':1}]}


class BatchBridge(Bridge):
    def __init__(self,effect='confirmed',new_owner=False):
        super().__init__([]);self.batch_calls=[];self.effect=effect;self.new_owner=new_owner
    def request(self,command,**kwargs):
        self.requests.append((command,kwargs))
        if command=='observe_tui_text':return two_fields()
        if command!='execute_batch_v1':raise AssertionError(command)
        self.batch_calls.append(kwargs);after=two_fields(2,True)
        if self.new_owner:
            after['observation']['generation']=2;after['tui_view']['generation']=2
            after['observation']['source_identity']['namespace']['generation']=2
        items=[{'operation_id':op['operation_id'],'receipt':{'accepted':True,'effect':self.effect}}
               for op in kwargs['operations'][:1 if self.effect=='unknown' else 2]]
        return {**after,'batch':{'version':'gui2tui.agent.batch.v1','status':'interrupted' if self.effect=='unknown' else 'completed','items':items,'reason':None}}


class IncrementalAndBatchTests(unittest.TestCase):
    def test_next_request_retains_exact_prefix_raw_reply_and_every_history_fact(self):
        client=Mock(config=DeepSeekConfig(api_key='test-only'),metadata={});requests=[]
        client.assistant_content=' { "kind" : "observe" } '
        client.complete_json.return_value={'kind':'observe'}
        planner=TuiPlanner(client,lambda raw:requests.append(json.loads(raw)) or 100,Budget(4,10000,40000))
        first=model_state('goal',frame(),['中文\n尾部'],[]);first['future']={'keep':[1,1.0,True,None]}
        planner.plan(first)
        second=copy.deepcopy(first);second['tui_view']['observation_id']=2
        second['history'].append({'plan':{'kind':'observe'},'receipt':{'delivery':'not_attempted'}})
        planner.plan(second)
        third=copy.deepcopy(second);del third['future'];third['history'].append({'receipt':{'effect':'unknown'}})
        planner.plan(third)
        for old,new in zip(requests,requests[1:]):
            self.assertEqual(new['messages'][:len(old['messages'])],old['messages'])
            self.assertEqual(new['messages'][len(old['messages'])]['content'],client.assistant_content)
        self.assertEqual(decode_request_state(json.dumps(requests[-1])),third)
        second_update=json.loads(requests[1]['messages'][-1]['content'])
        self.assertNotIn('tui_view',second_update['set'])
        self.assertEqual(second_update['view_set'],{'observation_id':2})
        tail=json.loads(requests[-1]['messages'][-1]['content'])
        self.assertEqual(len(tail['history_append']),1)
        self.assertIn('future',tail['remove'])
        changed=copy.deepcopy(third);changed['history'][0]={'rewritten':True}
        with self.assertRaises(ValueError):planner.plan(changed)
        self.assertEqual(client.complete_json.call_count,3)

    def test_done_checks_current_visible_facts_and_never_asserts_independent_completion(self):
        f=frame();validate_plan(done(),f,[])
        for evidence in [[],[{'kind':'node_state','target':11,'state':'Checked','present':True}],
                         [{'kind':'node_value','target':1,'value':'hidden'}]]:
            with self.assertRaises(ValueError):validate_plan({'kind':'done','evidence':evidence},f,[])
        b=Bridge([f]);p=Planner([done()]);result=run_tui('Already enabled',b,p,max_steps=1)
        self.assertEqual(result['status'],'model_completed');self.assertIsNone(result['task_completed'])
        self.assertEqual(b.executions,[])

    def test_invalid_model_plan_gets_no_write_feedback_and_one_fresh_decision(self):
        b=Bridge([frame(),frame(2)]);p=Planner([{'type':'json_object'},done()])
        result=run_tui('goal',b,p,max_steps=2)
        self.assertEqual(result['status'],'model_completed');self.assertEqual(b.executions,[])
        self.assertEqual(p.states[1]['history'][0]['delivery'],'not_attempted')
        self.assertIn('validation_error',p.states[1]['history'][0])

    def test_unchanged_observation_loop_stops_without_manufacturing_done(self):
        frames=[frame() for _ in range(3)]
        for i,f in enumerate(frames):f['observation']['observation_id']=i+1;f['tui_view']['observation_id']=i+1
        b=Bridge(frames);p=Planner([{'kind':'observe'}]*3)
        result=run_tui('goal',b,p,max_steps=8)
        self.assertEqual(result['status'],'stalled');self.assertIsNone(result['task_completed'])
        self.assertEqual(len(b.requests),3)

    def test_batch_uses_one_original_publication_and_requires_a_new_completion_decision(self):
        b=BatchBridge();p=Planner([batch(),done()])
        result=run_tui('two fields',b,p,literals=['first','second'],max_steps=2)
        self.assertEqual(result['status'],'model_completed');self.assertEqual(result['gui_operation_attempts'],2)
        self.assertEqual(len(b.batch_calls),1)
        self.assertEqual([x['operation_id'] for x in b.batch_calls[0]['operations']],['op-0','op-second'])
        self.assertEqual(p.states[1]['tui_view']['observation_id'],2)
        self.assertEqual(p.states[1]['history'][0]['receipt']['effect'],'confirmed')
        self.assertEqual(b.executions,[])

    def test_batch_rejects_unpublished_tail_duplicate_ids_and_action_budget_before_writing(self):
        f=two_fields()
        for proposal in [dict(kind='batch',operations=[batch()['operations'][0],{'operation_id':'future-control','literal_index':1}]),
                         dict(kind='batch',operations=[batch()['operations'][0]]*2)]:
            with self.assertRaises(ValueError):validate_plan(proposal,f,['a','b'])
        b=BatchBridge();p=Planner([batch(),{'kind':'abstain'}])
        result=run_tui('goal',b,p,literals=['a','b'],max_steps=2,max_actions=1)
        self.assertEqual(result['status'],'abstained');self.assertEqual(b.batch_calls,[])

    def test_unknown_batch_step_cannot_be_replayed_under_a_fresh_operation_id(self):
        b=BatchBridge(effect='unknown');p=Planner([batch(),{'kind':'execute','operation_id':'new-first','literal_index':0}])
        result=run_tui('goal',b,p,literals=['a','b'],max_steps=2)
        self.assertEqual(result['status'],'unknown');self.assertEqual(len(b.batch_calls),1)
        self.assertEqual(result['gui_operation_attempts'],1)

    def test_offscreen_recent_readback_can_prove_a_fact_but_cannot_authorize_execution(self):
        original=frame();identity=public_source_identity(original['observation'],11)
        history=[{'operation':original['observation']['operations'][0],'source_identity':identity,
                  'receipt':{'accepted':True,'effect':'unknown'}}]
        current=frame(2);current['tui_view']['visible_bindings']=[]
        current['observation']['nodes'][-1]['states'].append('Checked')
        state=model_state('enabled',current,[],history)
        readback=state['recent_operation_readbacks'][0]
        self.assertEqual(readback['status'],'observed');self.assertFalse(readback['execution_authority'])
        proposal={'kind':'done','evidence':[{'kind':'node_state','target':11,'state':'Checked','present':True}]}
        validate_plan(proposal,current,[],readback_targets=[readback['node']['id']])
        with self.assertRaises(ValueError):validate_plan({'kind':'execute','operation_id':'op-0'},current,[])
        # A new object with the same ID/label must not be silently used for readback.
        current['observation']['nodes'][-1]['locator_ref']='replacement-source'
        state=model_state('enabled',current,[],history)
        self.assertEqual(state['recent_operation_readbacks'][0]['status'],'unavailable')
        with self.assertRaises(ValueError):validate_plan(proposal,current,[])

    def test_batch_generation_change_stops_instead_of_rebinding(self):
        b=BatchBridge(new_owner=True);p=Planner([batch()])
        result=run_tui('goal',b,p,literals=['a','b'],max_steps=2)
        self.assertEqual(result['status'],'blocked');self.assertEqual(len(b.batch_calls),1)


if __name__=='__main__':unittest.main()
