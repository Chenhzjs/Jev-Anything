"""Protocol-preservation regressions; all decisions are deterministic local stubs."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import Mock

from jev_anything.document import (DOCUMENT_VERSION, SOURCE_IDENTITY_VERSION, read_document,
                                  public_text_comparison, public_source_identity,
                                  current_source_for_identity, invocable_operations, public_object_comparison)
from jev_anything.jev import JevClient, JevConfig
from jev_anything.native import (NativeBridge, NativeBridgeError, candidates_for,
                                 choose, run)


def document(serial=1):
    # One small structural fixture with deliberately long payload and many
    # candidates. It tests transport invariants, not a real GUI task score.
    doc = dict(version=DOCUMENT_VERSION, observation_id=serial, session='session',
               generation=1, interaction_scope=1, readable_scope=1,
               collection=dict(started_at_ms=serial, finished_at_ms=serial+1, atomic_snapshot=False),
               completeness=dict(materialization='complete_for_available_payloads', observed_coverage='partial', requires_expansion=False),
               execution_authority='current G2T registry only', shared_organization_policy='tui.document.v1',
               nodes=[], operations=[], relations=[], text_payloads=[], content=[],
               regions={'roots': []}, commands={'groups': []}, choices=[], scopes=[],
               sources=[], boundary_references=[], value_domains=[], document_probes=[],
               timings={'ax_walk_ms': serial}, future_public_field={'preserve': 'opaque metadata'})
    for i in range(12):
        doc['nodes'].append(dict(id=i, parent=i-1 if i else None, role='Container',
                                 label=None if i==7 else f'ancestor-{i}', states=[]))
    doc['text_payloads'] = [dict(source=11, read=dict(status='complete', text='公开正文' * 14000 + 'TAIL-FIRST')),
                            dict(source=10, read=dict(status='complete', text='SECOND-DOCUMENT-TAIL'))]
    doc['content'] = [dict(root=i, blocks=[dict(source=i, text={'payload_ref': {'text_source': i}})]) for i in [11,10]]
    doc['relations'] = [dict(source=11, read={'status':'known','relations':[{'kind':'labelled_by','target':10}]}),
                        dict(source=10, read={'status':'unavailable'})]
    doc['value_domains'] = [dict(source=11, read=dict(status='known', min=0, max=100, step=5))]
    for i in range(251):
        doc['operations'].append(dict(id=f'op-{i}', target=11, kind='action', name='activate',
            label='Same', label_provenance={'kind':'public_name','source':11},
            agent_invocable=True, parameter_domain={'kind':'none'}))
    doc['operations'] += [dict(id='edit', target=10, kind='replace_text', parameter='text',
                               agent_invocable=True, parameter_domain={'kind':'text'}),
                          dict(id='range', target=10, kind='edit_range', agent_invocable=False,
                               parameter_domain={'kind':'text_range','bounds':'unknown'})]
    return doc


def identity_document(serial=1):
    doc=document(serial)
    doc['source_identity']={'version':SOURCE_IDENTITY_VERSION,
                            'namespace':{k:doc[k] for k in ('session','generation')}}
    for n in doc['nodes']:n['locator_ref']=f'fixture-address-{n["id"]}'
    return doc


def remap_snapshot_ids(doc, offset=100):
    scalar_refs={'id','parent','target','owner','source','root','text_source','node_ref',
                 'interaction_scope','readable_scope'}
    def visit(value, key=None):
        if isinstance(value,dict):return {k:visit(v,k) for k,v in value.items()}
        if isinstance(value,list):return [visit(v,'id' if key in ('children','roots') else None) for v in value]
        return value+offset if key in scalar_refs and type(value) is int else value
    return visit(doc)


class Stub:
    def __init__(self, answers=('abstain',), status=200):
        self.requests=[];self.answers=iter(answers);self.status=status
    def __enter__(self):
        stub=self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']))
                stub.requests.append(json.loads(raw))
                answer=next(stub.answers, 'abstain')
                body=json.dumps({'answers':{'action':{'type':'choice','choice':answer}}}).encode()
                self.send_response(stub.status);self.send_header('Content-Length',str(len(body)))
                self.send_header('X-Request-ID','local-stub');self.end_headers();self.wfile.write(body)
            def log_message(self,*args): pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=JevClient(JevConfig(api_key='stub-only', api_url=f'http://127.0.0.1:{self.server.server_port}/decisions'))
        return self
    def __exit__(self,*args):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)


class DocumentTests(unittest.TestCase):
    def test_object_inventory_comparison_preserves_exact_addresses_and_does_not_infer_deletion(self):
        before = identity_document(); after = remap_snapshot_ids(before); after['observation_id'] = 2
        self.assertEqual(public_object_comparison(before, after)['changed'], [])
        before['nodes'][11].update(value='OLD_VALUE_NOT_EXPORTED', description='OLD_DESCRIPTION_NOT_EXPORTED')
        after['nodes'] = [n for n in after['nodes'] if n['id'] != 111]
        after['nodes'][10]['states'] = ['Selected']
        comparison = public_object_comparison(before, after)
        rows = {r['locator_ref']: r for r in comparison['changed']}
        self.assertIsNone(rows['fixture-address-11']['after'])
        self.assertEqual(rows['fixture-address-10']['after']['states'], ['Selected'])
        self.assertEqual(comparison['after_completeness']['observed_coverage'], 'partial')
        self.assertIn('not proof of deletion', comparison['absence_meaning'])
        self.assertFalse(comparison['is_execution_authority'])
        encoded = json.dumps(comparison)
        for marker in ('OLD_VALUE_NOT_EXPORTED', 'OLD_DESCRIPTION_NOT_EXPORTED', 'TAIL-FIRST'):
            self.assertNotIn(marker, encoded)
        for mutation in ('generation', 'scope', 'identity', 'redacted'):
            bad = copy.deepcopy(after)
            if mutation == 'generation': bad['generation'] += 1
            elif mutation == 'scope': bad['nodes'][1]['locator_ref'] = 'different-window'
            elif mutation == 'identity': bad['nodes'][0]['locator_ref'] = bad['nodes'][1]['locator_ref']
            else:
                bad['nodes'][0]['redacted'] = True
                with self.assertRaises(ValueError): public_object_comparison(before, bad)
                continue
            self.assertTrue(public_object_comparison(before, bad)['availability'].startswith('unavailable'))

    def test_locator_comparison_handles_new_snapshot_keys_without_rebinding_operations(self):
        before=identity_document();after=remap_snapshot_ids(before);after['observation_id']=2
        before['operations'].append({**before['operations'][-2],'id':'other-edit','target':11})
        after['operations'].append({**after['operations'][-2],'id':'other-edit','target':111})
        after['text_payloads'][1]['read']['text']='new current public value'
        saved=copy.deepcopy((before,after));comparison=public_text_comparison(before,after)
        self.assertEqual(comparison['version'],'jev.public-text-comparison.v2')
        self.assertEqual(comparison['availability'],'complete_for_declared_text_values')
        self.assertTrue(comparison['same_declared_objects'])
        self.assertEqual({r['source']:r['exported_text_equal_to_previous'] for r in comparison['targets']},{110:False,111:True})
        identity=public_source_identity(before,10)
        self.assertEqual(current_source_for_identity(after,identity),110)
        self.assertEqual((before,after),saved)
        self.assertFalse(comparison['is_execution_authority'])
        self.assertEqual(comparison['independent_task_completion'],'not_assessed')
        changed=copy.deepcopy(after);changed['nodes'][10]['locator_ref']='different-address'
        result=public_text_comparison(before,changed)
        self.assertIsNone(result['targets'][0]['exported_text_equal_to_previous'])
        self.assertEqual(result['availability'],'partial')
        self.assertIsNone(current_source_for_identity(changed,identity))
        # A missing read does not erase the other exact, complete comparison.
        partial=copy.deepcopy(after);partial['text_payloads'][1]['read']={'status':'unavailable'}
        result=public_text_comparison(before,partial)
        self.assertEqual([r['exported_text_equal_to_previous'] for r in result['targets']],[None,True])

    def test_locator_comparison_rejects_ambiguous_scope_and_does_not_export_removed_sources(self):
        before=identity_document();after=copy.deepcopy(before);after['observation_id']=2
        for mutation in ('missing','duplicate','namespace','scope','invalid-target'):
            bad=copy.deepcopy(after)
            if mutation=='missing':bad['nodes'][10].pop('locator_ref')
            elif mutation=='duplicate':bad['nodes'][10]['locator_ref']=bad['nodes'][11]['locator_ref']
            elif mutation=='namespace':bad['source_identity']['namespace']['generation']=True
            elif mutation=='scope':bad['nodes'][1]['locator_ref']='another-scope-address'
            else:bad['operations'][-2]['target']={}
            result=public_text_comparison(before,bad)
            self.assertTrue(result['availability'].startswith('unavailable'))
            self.assertEqual(len(list(invocable_operations(bad))),len(list(invocable_operations(after))))
        before['nodes'][10]['locator_ref']='REMOVED_SOURCE_REF'
        before['text_payloads'][1]['read']['text']='PREVIOUS_PRIVATE_TEXT'
        current=copy.deepcopy(after);current['nodes']=[n for n in current['nodes'] if n['id']<10]
        current['operations']=[];current['text_payloads']=[]
        comparison=public_text_comparison(before,current)
        self.assertEqual(comparison['targets'],[])
        self.assertNotIn('REMOVED_SOURCE_REF',json.dumps(comparison))
        self.assertNotIn('PREVIOUS_PRIVATE_TEXT',json.dumps(comparison))
        self.assertIsNone(current_source_for_identity(current,public_source_identity(before,10)))

    def test_public_text_comparison_is_scoped_literal_evidence_without_old_payload(self):
        before=document(1);before['operations'].append(dict(before['operations'][-2],id='other-edit',target=11))
        after=copy.deepcopy(before);after['observation_id']=2
        after['text_payloads'][1]['read']['text']='changed public text'
        original=copy.deepcopy((before,after));result=public_text_comparison(before,after)
        self.assertEqual((before,after),original)
        self.assertEqual(result['availability'],'complete_for_declared_text_values')
        self.assertEqual({row['source']:row['exported_text_equal_to_previous'] for row in result['targets']},{10:False,11:True})
        self.assertFalse(result['is_task_completion']);self.assertFalse(result['is_execution_authority'])
        self.assertNotIn('changed public text',json.dumps(result));self.assertNotIn('SECOND-DOCUMENT-TAIL',json.dumps(result))
        after['text_payloads'][1]['read']['status']='unavailable'
        self.assertIsNone(public_text_comparison(before,after)['targets'][0]['exported_text_equal_to_previous'])
        after['generation']=2
        self.assertEqual(public_text_comparison(before,after)['availability'],'unavailable_scope_or_generation_change')

    def test_current_private_subtree_cannot_export_prior_text_hash_or_removed_reference(self):
        before=document(1);secret='NEVER-EXPORT-OLD-TEXT'
        before['text_payloads'][1]['read']['text']=secret
        after=copy.deepcopy(before);after['observation_id']=2
        after['nodes']=[row for row in after['nodes'] if row['id']<10]
        for field in ['operations','relations','text_payloads','content','value_domains']:
            after[field]=[]
        result=public_text_comparison(before,after);encoded=json.dumps(result)
        self.assertEqual(result['targets'],[]);self.assertEqual(result['availability'],'partial')
        self.assertNotIn(secret,encoded);self.assertNotIn('hash',encoded);self.assertNotIn('character_count',encoded)

    def test_actual_http_request_preserves_document_candidates_domains_and_history(self):
        doc=document();before=copy.deepcopy(doc)
        receipt={'accepted':True,'effect':'confirmed','delivery':'accepted',
                 'readback':{'text':'earlier full text'},'timings':{'fresh_validation_ms':17},
                 'message':'full receipt','observation_id':0,'future_evidence':{'source':'AX'}}
        history=[{'operation':{'id':'earlier','operation_id':'earlier','parameter':'literal',
                              'parameter_domain':{'kind':'text'}},'receipt':receipt}]
        candidates=candidates_for(doc,['exact literal'])
        with Stub() as stub:
            choose(stub.client,'Read and act',doc,candidates,history)
        self.assertEqual(len(stub.requests),1)
        request=stub.requests[0]
        self.assertEqual(request['state']['accessibility'],doc)
        self.assertEqual(request['state']['history'],history)
        self.assertGreater(len(json.dumps(request).encode()),65536)
        criteria=request['questions']['action']['criteria']
        self.assertEqual(len(criteria),251+1+3)
        self.assertNotIn('range',criteria)
        self.assertIn(doc['operations'][-1],request['state']['accessibility']['operations'])
        self.assertEqual(json.loads(criteria['edit-p0'])['parameter'],'exact literal')
        self.assertEqual(request['state']['candidate_representation'],'gui2tui.operation_refs.v1')
        operations={operation['id']:operation for operation in request['state']['accessibility']['operations']}
        self.assertEqual(json.loads(criteria['edit-p0'])['operation_ref'],'edit')
        self.assertEqual(operations['edit']['parameter_domain'],{'kind':'text'})
        for candidate in candidates:
            reference=json.loads(criteria[candidate['id']])
            self.assertEqual(operations[reference['operation_ref']],
                             next(op for op in doc['operations'] if op['id']==candidate['operation_id']))
            self.assertEqual(set(reference),{'operation_ref','parameter'} if 'parameter' in candidate else {'operation_ref'})
        choice=json.loads(criteria['op-250'])
        self.assertEqual(operations[choice['operation_ref']]['label_provenance'],doc['operations'][250]['label_provenance'])
        nodes={node['id']:node for node in request['state']['accessibility']['nodes']}
        chain=[];target=operations[choice['operation_ref']]['target']
        while target is not None:
            chain.append(nodes[target]);target=nodes[target]['parent']
        self.assertEqual(len(chain)-1,11)
        self.assertEqual(doc,before)

    def test_reference_literal_dispatch_keeps_original_candidate_and_full_history(self):
        doc=document()
        bridge=Mock(snapshot=Mock(side_effect=[doc, document(2)]),
                    execute=Mock(return_value={'accepted':True,'effect':'confirmed','readback':{'text':'literal B'}}))
        with Stub(answers=['edit-p1','done']) as stub:
            result=run('Set literal B',bridge,stub.client,texts=['literal A','literal B'])
        self.assertEqual(len(stub.requests),2)
        first=stub.requests[0]['questions']['action']['criteria']
        self.assertEqual(json.loads(first['edit-p0']),{'operation_ref':'edit','parameter':'literal A'})
        self.assertEqual(json.loads(first['edit-p1']),{'operation_ref':'edit','parameter':'literal B'})
        selected=bridge.execute.call_args.args[1]
        self.assertEqual(selected['operation_id'],'edit')
        self.assertEqual(selected['parameter'],'literal B')
        self.assertEqual(selected['parameter_domain'],{'kind':'text'})
        self.assertEqual(stub.requests[1]['state']['history'],result['history'])
        self.assertIsNone(result['task_completed'])

    def test_missing_reference_fails_before_provider_or_dispatch(self):
        doc=document();candidates=candidates_for(doc);candidates[0]['operation_id']='absent'
        provider=Mock()
        with self.assertRaises(ValueError):choose(provider,'Act',doc,candidates,[])
        provider.decide.assert_not_called()

    def test_document_selection_is_explicit_without_legacy_fallback(self):
        bridge=object.__new__(NativeBridge);bridge.observation_format='document'
        bridge.request=Mock(return_value={'observation':document()})
        self.assertEqual(bridge.snapshot()['version'],DOCUMENT_VERSION)
        bridge.request.assert_called_once_with('observe_document')
        bridge.request=Mock(side_effect=NativeBridgeError({'delivery':'not_attempted','error':'unsupported command'}))
        with self.assertRaises(NativeBridgeError):bridge.snapshot()
        bridge.request.assert_called_once_with('observe_document')
        bridge.observation_format='v1';bridge.request=Mock(return_value={'observation':{'version':'gui2tui.agent.v1'}})
        bridge.snapshot();bridge.request.assert_called_once_with('observe')

    def test_bad_document_is_rejected_instead_of_partially_sanitized(self):
        doc=document();doc['nodes'][1]['redacted']=True
        with self.assertRaises(ValueError):read_document(doc)
        doc=document();del doc['text_payloads']
        with self.assertRaises(ValueError):read_document(doc)
        doc=document();doc['version']='gui2tui.agent.document.v999'
        provider=Mock();result=run('Read',Mock(snapshot=Mock(return_value=doc)),provider)
        self.assertEqual(result['status'],'failed');provider.decide.assert_not_called()

    def test_unknown_unchanged_facts_ignore_acquisition_timing_and_never_replay(self):
        bridge=Mock(snapshot=Mock(side_effect=[document(1),document(2)]),
                    execute=Mock(return_value={'accepted':True,'effect':'unknown'}))
        with Stub(answers=['op-0']) as stub:
            result=run('Activate',bridge,stub.client)
        self.assertEqual(result['status'],'unknown');self.assertIsNone(result['task_completed'])
        self.assertEqual(len(stub.requests),1);self.assertEqual(bridge.execute.call_count,1)
        self.assertEqual(result['history'][0]['receipt']['effect'],'unknown')

    def test_not_attempted_requires_fresh_decision_and_preserves_rejection(self):
        first=document(1);second=document(2);second['operations'][0]['id']='fresh-op'
        rejection={'ok':False,'delivery':'not_attempted','error':'stale exact target','future_evidence':{'generation':1}}
        bridge=Mock(snapshot=Mock(side_effect=[first,second]),
                    execute=Mock(side_effect=NativeBridgeError(rejection)))
        with Stub(answers=['op-0','done']) as stub:
            result=run('Activate',bridge,stub.client)
        self.assertEqual(result['status'],'model_completed');self.assertIsNone(result['task_completed'])
        self.assertEqual(bridge.execute.call_count,1);self.assertEqual(len(stub.requests),2)
        self.assertEqual(stub.requests[1]['state']['accessibility'],second)
        self.assertEqual(stub.requests[1]['state']['history'][0]['receipt'],rejection)
        self.assertNotIn('op-0',stub.requests[1]['questions']['action']['criteria'])

    def test_http_rejection_keeps_complete_input_without_retry_or_dispatch(self):
        doc=document();bridge=Mock(snapshot=Mock(return_value=doc));events=[]
        with Stub(status=413) as stub:
            result=run('Read',bridge,stub.client,emit=events.append)
        self.assertEqual(result['status'],'failed');bridge.execute.assert_not_called()
        self.assertEqual(len(stub.requests),1)
        self.assertEqual(stub.requests[0]['state']['accessibility'],doc)
        event=next(e for e in events if e['kind']=='decision_request')
        self.assertEqual(event['state'],stub.requests[0]['state'])
        self.assertEqual(next(e for e in events if e['kind']=='decision_error')['usage']['http_status'],413)

    def test_receipt_survives_failed_fresh_readback(self):
        bridge=Mock(snapshot=Mock(side_effect=[document(),RuntimeError('read unavailable')]),
                    execute=Mock(return_value={'accepted':True,'effect':'confirmed','readback':{'text':'full evidence'}}))
        with Stub(answers=['op-0']) as stub:result=run('Activate',bridge,stub.client)
        self.assertEqual(result['status'],'unknown')
        self.assertEqual(result['history'][0]['receipt']['readback'],{'text':'full evidence'})

    def test_annotation_observation_provenance_does_not_fake_a_gui_change(self):
        for version in ('tui.decision_annotations.v1','tui.decision_annotations.v2'):
            with self.subTest(version=version):
                docs=[document(1),document(2)]
                for doc in docs:
                    doc['decision_annotations']={'version':version,
                        'observation_id':doc['observation_id'],'session':doc['session'],
                        'generation':doc['generation'],'cohorts':[],'task_relevance':'not_evaluated'}
                bridge=Mock(snapshot=Mock(side_effect=docs),
                            execute=Mock(return_value={'accepted':True,'effect':'unknown'}))
                with Stub(answers=['op-0']) as stub:result=run('Activate',bridge,stub.client)
                self.assertEqual(result['status'],'unknown')
                self.assertEqual(len(stub.requests),1)
                self.assertEqual(bridge.execute.call_count,1)
