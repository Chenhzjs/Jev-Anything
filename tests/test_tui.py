import copy
import json
import unittest
from unittest.mock import Mock

from test_document import identity_document, remap_snapshot_ids
from jev_anything.deepseek import DeepSeekConfig
from jev_anything.jev import JevError
from jev_anything.native import NativeBridgeError
from jev_anything.tui import (VIEW_VERSION, Budget, BudgetExceeded, TuiPlanner,
                             checked_view, model_state, run_tui, validate_plan,
                             encode_request, decode_request_state)


def frame(serial=1, remap=False, operation='op-0'):
    doc = identity_document(serial)
    if remap: doc = remap_snapshot_ids(doc)
    target = 111 if remap else 11
    doc['nodes'][-1].update(role='Button',label='Public control',value=str(serial),states=['Enabled'])
    doc['operations'][0]['id'] = operation
    view = {'version':VIEW_VERSION,'complete_document':False,'text':'[Public control]',
            **{k:doc[k] for k in ('observation_id','session','generation','interaction_scope')},
            'visible_bindings':[{'target':target,'operations':[doc['operations'][0]]}],
            'navigation_tools':{'actions':['find_action','next_control']}}
    return {'ok':True,'observation':doc,'tui_view':view,
            'navigation':{'gui_write':False,'activation':'not_attempted','status':'focused'}}


class Bridge:
    def __init__(self, frames, receipt=None, rejected=None):
        self.frames=iter(frames);self.requests=[];self.executions=[]
        self.receipt=receipt or {'accepted':True,'effect':'confirmed'};self.rejected=rejected
    def request(self, command, **kwargs):
        self.requests.append((command,kwargs));return copy.deepcopy(next(self.frames))
    def execute(self, observation, candidate):
        self.executions.append((observation['observation_id'],candidate))
        if self.rejected:raise NativeBridgeError(self.rejected)
        return self.receipt


class Planner:
    def __init__(self, plans):self.plans=iter(plans);self.states=[]
    def plan(self,state):self.states.append(copy.deepcopy(state));return next(self.plans)


class TuiTests(unittest.TestCase):
    def test_navigation_uses_fresh_reference_and_keeps_full_history_without_raw_document(self):
        b=Bridge([frame(1),frame(2),frame(3)])
        p=Planner([{'kind':'navigate','action':'find_action','query':'Public control'},
                   {'kind':'execute','operation_id':'op-0'}, {'kind':'done','evidence':[{'kind':'view_text','text':'Public control'}]}])
        result=run_tui('A goal',b,p,max_steps=3)
        self.assertEqual(result['status'],'model_completed');self.assertIsNone(result['task_completed'])
        self.assertEqual(b.executions[0][0],2)
        self.assertNotIn('accessibility',p.states[0]);self.assertNotIn('TAIL-FIRST',json.dumps(p.states))
        self.assertEqual(len(p.states[-1]['history']),2)
        self.assertEqual(p.states[-1]['visible_public_state'][0]['states'],['Enabled'])

    def test_invented_id_missing_endpoint_and_generated_write_text_are_rejected(self):
        f=frame()
        for plan in [{'kind':'execute','operation_id':'invented'},
                     {'kind':'execute','operation_id':'op-0','parameter':'not-user-data'},
                     {'kind':'navigate','action':'raw_keys','query':'Enter'}]:
            with self.assertRaises(ValueError):validate_plan(plan,f,[])
        broken=copy.deepcopy(f);broken['tui_view']['visible_bindings'][0]['target']=9999
        with self.assertRaises(ValueError):checked_view(broken)
        protected=copy.deepcopy(f);protected['observation']['nodes'][-1]['text_input_kind']='Password'
        with self.assertRaises(ValueError):model_state('goal',protected,[],[])

    def test_reader_overlay_preserves_text_and_cannot_invoke_hidden_gui_controls(self):
        f=frame();f['tui_view']['reader']={'root':11,'mode':'Reader'}
        with self.assertRaises(ValueError):checked_view(f)
        f['tui_view']['visible_bindings']=[];f['tui_view']['text']='Reader public TAIL'
        f['tui_view']['navigation_tools']['actions']=['find_text','close_reader']
        state=model_state('goal',f,[],[])
        self.assertEqual(state['tui_view']['text'],'Reader public TAIL')
        validate_plan({'kind':'navigate','action':'find_text','query':'TAIL'},f,[])
        with self.assertRaises(ValueError):validate_plan({'kind':'execute','operation_id':'op-0'},f,[])
        f['tui_view']['reader']['root']=9999
        with self.assertRaises(ValueError):checked_view(f)

    def test_parameter_is_exact_user_literal_only(self):
        f=frame();op=f['observation']['operations'][0]
        op.update(kind='replace_text',parameter_domain={'kind':'text'})
        plan={'kind':'execute','operation_id':'op-0','literal_index':0}
        validate_plan(plan,f,['user literal'])
        with self.assertRaises(ValueError):validate_plan(plan,f,[])

    def test_unknown_source_cannot_be_replayed_under_new_node_and_operation_ids(self):
        b=Bridge([frame(1),frame(2,remap=True,operation='new-op')],receipt={'accepted':True,'effect':'unknown'})
        p=Planner([{'kind':'execute','operation_id':'op-0'}, {'kind':'execute','operation_id':'new-op'}])
        result=run_tui('goal',b,p,max_steps=2)
        self.assertEqual(result['status'],'unknown');self.assertIn('not replayed',result['reason'])
        self.assertEqual(len(b.executions),1)

    def test_unknown_unchanged_state_allows_a_different_current_public_action(self):
        f=frame(1);op=copy.deepcopy(f['observation']['operations'][0])
        op.update(id='other-op',name='Other public action')
        f['observation']['operations'].append(op)
        f['tui_view']['visible_bindings'][0]['operations'].append(op)
        same=copy.deepcopy(f);same['observation']['observation_id']=2;same['tui_view']['observation_id']=2
        changed=copy.deepcopy(same);changed['observation']['nodes'][-1]['value']='changed'
        class Receipts(Bridge):
            def execute(self,observation,candidate):
                self.receipt={'accepted':True,'effect':'unknown' if not self.executions else 'confirmed'}
                return super().execute(observation,candidate)
        b=Receipts([f,same,changed]);p=Planner([{'kind':'execute','operation_id':'op-0'},
            {'kind':'execute','operation_id':'other-op'},{'kind':'abstain'}])
        result=run_tui('goal',b,p,max_steps=3)
        self.assertEqual(result['status'],'abstained')
        self.assertEqual([c['operation_id'] for _,c in b.executions],['op-0','other-op'])
        self.assertFalse(p.states[1]['observation_progress']['public_state_changed'])
        self.assertEqual(p.states[1]['history'][0]['receipt']['effect'],'unknown')

    def test_not_attempted_reobserves_and_requires_new_decision(self):
        b=Bridge([frame(1),frame(2)],rejected={'ok':False,'delivery':'not_attempted','error':'Stale'})
        p=Planner([{'kind':'execute','operation_id':'op-0'},{'kind':'abstain'}])
        result=run_tui('goal',b,p,max_steps=2)
        self.assertEqual(result['status'],'abstained');self.assertEqual(len(b.executions),1)
        self.assertEqual(p.states[-1]['tui_view']['observation_id'],2)
        self.assertEqual(p.states[-1]['history'][0]['receipt']['delivery'],'not_attempted')

    def test_unchanged_observation_feedback_is_public_change_not_task_success(self):
        first=frame(1);second=copy.deepcopy(first)
        second['observation']['observation_id']=2;second['tui_view']['observation_id']=2
        b=Bridge([first,second]);p=Planner([{'kind':'observe'},{'kind':'abstain'}])
        result=run_tui('goal',b,p,max_steps=2)
        self.assertEqual(result['status'],'abstained')
        self.assertIsNone(p.states[0]['observation_progress']['public_state_changed'])
        self.assertFalse(p.states[1]['observation_progress']['public_state_changed'])
        self.assertEqual(p.states[1]['observation_progress']['consecutive_unchanged_observations'],1)
        self.assertEqual(len(p.states[1]['history']),1)
        self.assertEqual(b.executions,[])

    def test_budget_stops_before_provider_without_cropping_history(self):
        client=Mock(config=DeepSeekConfig(api_key='test-only'),metadata={})
        events=[];p=TuiPlanner(client,lambda raw:100,Budget(1,50,1000),emit=events.append)
        state={'history':[{'large':'complete history'*1000}]}
        with self.assertRaises(BudgetExceeded):p.plan(state)
        client.complete_json.assert_not_called()
        self.assertEqual(events[0]['state'],state)

    def test_agent_handoff_reobserves_keeps_history_and_uses_only_new_visible_ids(self):
        b=Bridge([frame(1),frame(2),frame(3,operation='current-human-op'),frame(4)])
        p=Planner([{'kind':'handoff','instructions':'Use original GUI'},
                   {'kind':'execute','operation_id':'current-human-op'},{'kind':'abstain'}])
        events=[]
        def human(request):
            self.assertEqual(b.executions,[])
            self.assertEqual(request['instructions'],'Use original GUI')
            return 'resume'
        result=run_tui('goal',b,p,max_steps=3,human_handler=human,emit=events.append)
        self.assertEqual(result['status'],'abstained');self.assertEqual(b.executions[0][0],3)
        self.assertTrue(p.states[0]['human_interaction']['available'])
        self.assertEqual(p.states[1]['history'][0]['human_response'],'resume')
        self.assertEqual(p.states[1]['tui_view']['observation_id'],3)
        self.assertIsNone(result['task_completed'])

    def test_agent_handoff_does_not_clear_unknown_identity_guards(self):
        b=Bridge([frame(1),frame(2),frame(3),frame(4,remap=True,operation='after-human')],
                 receipt={'accepted':True,'effect':'unknown'})
        p=Planner([{'kind':'execute','operation_id':'op-0'},
                   {'kind':'handoff','instructions':'Inspect original GUI'},
                   {'kind':'execute','operation_id':'after-human'}])
        result=run_tui('goal',b,p,max_steps=3,human_handler=lambda _: 'resume')
        self.assertEqual(result['status'],'unknown');self.assertEqual(len(b.executions),1)
        self.assertIn('not replayed',result['reason'])

    def test_agent_handoff_missing_cancelled_or_changed_owner_never_executes(self):
        for handler,status in [(None,'needs_human'),(lambda _: 'cancel','human_cancelled')]:
            b=Bridge([frame(1),frame(2)]);p=Planner([{'kind':'handoff','instructions':'Manual GUI'}])
            result=run_tui('goal',b,p,max_steps=1,human_handler=handler)
            self.assertEqual(result['status'],status);self.assertEqual(b.executions,[])
        changed=frame(3);changed['observation']['generation']={'changed':True};changed['tui_view']['generation']={'changed':True}
        b=Bridge([frame(1),frame(2),changed]);p=Planner([{'kind':'handoff','instructions':'Manual GUI'}])
        result=run_tui('goal',b,p,max_steps=1,human_handler=lambda _: 'resume')
        self.assertEqual(result['status'],'blocked');self.assertEqual(b.executions,[])


class TuiEncodingTests(unittest.TestCase):
    def test_both_encodings_preserve_types_order_ids_tail_and_unknown_fields(self):
        f=frame();state=model_state('Keep all public evidence',f,['中文末尾 TAIL'],[
            {'receipt':{'accepted':True,'effect':'unknown'}},
            {'receipt':{'delivery':'not_attempted'}}])
        # Tag-shaped user data and future fields must remain literal data.
        state['future']={'input_encoding':'jev.tui-columns.v1','state_packet':[0,[-1,0]],
                         '$ref':'literal', 'numeric':[1,1.0,True,None,-0.0]}
        state['tui_view']['text']='Public body '*1000+'正文尾部 TAIL'
        op=state['tui_view']['visible_bindings'][0]['operations'][0]
        op['parameter_domain']={'kind':'number','minimum':-1,'maximum':100,'step':0.5}
        state['repeated']=[copy.deepcopy(op),copy.deepcopy(op)]
        original=copy.deepcopy(state)
        canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False)
        for encoding in ('plain','columns-v1'):
            raw=encode_request(DeepSeekConfig(api_key='test-only'),state,encoding)
            self.assertEqual(canonical(decode_request_state(raw,encoding)),canonical(state))
            self.assertEqual(canonical(state),canonical(original))
            request=json.loads(raw)
            self.assertEqual(request['thinking'],{'type':'disabled'})
            self.assertEqual(request['response_format'],{'type':'json_object'})
            self.assertIn('op-0',request['messages'][1]['content'])

    def test_invalid_encoding_and_missing_shared_endpoint_are_rejected(self):
        config=DeepSeekConfig(api_key='test-only')
        with self.assertRaises(ValueError):encode_request(config,{},'guessed')
        raw=encode_request(config,{'future':True},'columns-v1')
        request=json.loads(raw);payload=json.loads(request['messages'][1]['content'])
        payload['state_packet']['data']=[0,[-1,99999]]
        request['messages'][1]['content']=json.dumps(payload)
        with self.assertRaises(JevError):decode_request_state(json.dumps(request),'columns-v1')
        with self.assertRaises(ValueError):decode_request_state(raw,'guessed')
        # Even encoding-like source keys cannot collide with explicit decoder mode.
        source={'input_encoding':'jev.tui-columns.v1','state_packet':'user literal'}
        self.assertEqual(decode_request_state(encode_request(config,source)),source)

    def test_planner_counts_the_actual_packet_and_retains_it_before_budget_stop(self):
        client=Mock(config=DeepSeekConfig(api_key='test-only'),metadata={})
        state={'history':[{'large':'完整历史 '*1000}],'future':{'ordered':[3,2,1]}}
        counted=[];events=[]
        def counter(raw):counted.append(raw);return 100
        planner=TuiPlanner(client,counter,Budget(1,163,1000),emit=events.append,
                           input_encoding='columns-v1')
        with self.assertRaises(BudgetExceeded):planner.plan(state)
        client.complete_json.assert_not_called()
        self.assertEqual(decode_request_state(counted[0],'columns-v1'),state)
        self.assertEqual(json.loads(counted[0]),events[0]['request'])
        self.assertEqual(events[0]['input_encoding'],'columns-v1')
        self.assertEqual(events[0]['estimated_prompt_tokens_with_reserve'],164)
        client.complete_json.return_value={'kind':'observe'}
        planner=TuiPlanner(client,counter,Budget(1,164,1000),input_encoding='columns-v1')
        self.assertEqual(planner.plan(state),{'kind':'observe'})
        client.complete_json.assert_called_once_with(counted[-1])


if __name__=='__main__':unittest.main()
