import copy
import json
import unittest
from unittest.mock import Mock

import requests

from jev_anything.deepseek import DeepSeekClient, DeepSeekConfig, encode_deepseek_request, decode_deepseek_input
from jev_anything.jev import JevError


class DeepSeekTests(unittest.TestCase):
    def response(self, answers=None, **change):
        body = {'id':'test-request','model':'test-version','usage':{'prompt_tokens':100},
                'choices':[{'finish_reason':'stop','message':{'content':json.dumps(
                    {'answers':answers if answers is not None else {'action':{'type':'choice','choice':'id-285'}}})}}]}
        body.update(change)
        r=requests.Response();r.status_code=200;r._content=json.dumps(body).encode()
        return r

    def test_cache_layout_changes_only_object_order_and_retains_fresh_metadata(self):
        self.assertEqual(DeepSeekConfig(api_key='test-only').input_layout,'cache-prefix-v1')
        state={'goal':'A goal','accessibility':{'collection':{'started_at_ms':1},
            'observation_id':7,'future':{'unknown':[None,True,'Ω']},
            'nodes':[{'id':9,'states':['Focused']}],
            'operations':[{'id':'opaque','target':9}]},'history':[{'receipt':{'effect':'unknown'}}]}
        original=copy.deepcopy(state);questions={'action':{'type':'choice','criteria':{'opaque':'Exact operation'}}}
        decoded=[]
        for layout in ('canonical','cache-prefix-v1'):
            raw=encode_deepseek_request('deepseek-flash',state,questions,input_layout=layout)
            decoded.append(json.loads(json.loads(raw)['messages'][1]['content']))
        self.assertEqual(decoded[0],decoded[1])
        self.assertEqual(decoded[1],{'state':original,'questions':questions})
        self.assertEqual(list(decoded[1]['state']['accessibility'])[:2],['operations','nodes'])
        self.assertEqual(state,original)
        self.assertEqual(decoded[1]['state']['accessibility']['observation_id'],7)
        self.assertEqual(decoded[1]['state']['history'][0]['receipt']['effect'],'unknown')

    def test_lossless_full_packet_keeps_unknowns_types_ids_tail_and_every_candidate(self):
        state={'accessibility':{'nodes':[{'id':i,'label':None,'states':['Focused'] if i==0 else [],
                'unknown_future':{'zero':0,'flag':False,'body':'公开完整内容 Ω'*30}}
                for i in range(286)],'observation_id':9,'collection':{'atomic_snapshot':False},
                'text_payloads':[{'source':285,'read':{'status':'complete','text':'正文'*5000+'PUBLIC TAIL'}}]},
                'history':[{'receipt':{'effect':'unknown','accepted':None}}],'goal':'Use exact public source'}
        questions={'action':{'type':'choice','criteria':{f'opaque/{i:04d}-p0':f'Exact {i}' for i in range(286)}}}
        original=copy.deepcopy({'state':state,'questions':questions})
        normal=encode_deepseek_request('deepseek-flash',**original,input_layout='cache-prefix-v1')
        packed=encode_deepseek_request('deepseek-flash',**original,input_layout='lossless-state-v1')
        wire=json.loads(packed)
        self.assertEqual(decode_deepseek_input(wire['messages'][1]['content']),original)
        self.assertEqual({'state':state,'questions':questions},original)
        self.assertLess(len(packed),len(normal))
        self.assertIn('lossless-state-v1',wire['messages'][0]['content'])
        self.assertEqual(len(decode_deepseek_input(wire['messages'][1]['content'])['questions']['action']['criteria']),286)

    def test_single_large_body_retains_all_facts_candidates_and_history(self):
        state={'body':'公开正文 Ω\n'*10000+'TAIL','history':[{'unknown':True}]}
        questions={'action':{'type':'choice','criteria':{f'id-{i}':f'Exact target {i}' for i in range(286)}}}
        original=copy.deepcopy((state,questions))
        http=Mock(post=Mock(return_value=self.response()))
        client=DeepSeekClient(DeepSeekConfig(api_key='test-only'),session=http)
        self.assertEqual(client.decide(state=state,questions=questions)['action']['choice'],'id-285')
        raw=http.post.call_args.kwargs['data'];self.assertGreater(len(raw),65536)
        wire=json.loads(raw);received=decode_deepseek_input(wire['messages'][1]['content'])
        self.assertEqual(received,{'state':state,'questions':questions})
        self.assertEqual((state,questions),original)
        self.assertEqual(wire['thinking'],{'type':'disabled'})
        self.assertFalse(http.post.call_args.kwargs['allow_redirects'])
        http.post.assert_called_once()

    def test_unknown_choice_empty_or_truncated_output_is_rejected_without_retry(self):
        q={'action':{'type':'choice','criteria':{'legal':'One exact legal ID'}}}
        invalid=[self.response({'action':{'type':'choice','choice':'invented'}}),
                 self.response({'other':{'type':'choice','choice':'legal'}}),
                 self.response(choices=[{'finish_reason':'length','message':{'content':'{}'}}]),
                 self.response(choices=[{'finish_reason':'stop','message':{'content':''}}])]
        for response in invalid:
            http=Mock(post=Mock(return_value=response))
            with self.assertRaises(JevError):
                DeepSeekClient(DeepSeekConfig(api_key='test-only'),session=http).decide(state={},questions=q)
            http.post.assert_called_once()

    def test_rejection_preserves_fresh_metadata_without_key_or_old_usage(self):
        r=requests.Response();r.status_code=413;r.url='https://provider.invalid/chat/completions'
        http=Mock(post=Mock(return_value=r));client=DeepSeekClient(DeepSeekConfig(api_key='test-only'),session=http)
        client.metadata={'usage':{'old':True}}
        with self.assertRaises(JevError):client.decide(state={},questions={})
        self.assertEqual(client.metadata['http_status'],413)
        self.assertNotIn('usage',client.metadata)
        self.assertNotIn('test-only',json.dumps(client.metadata))
        http.post.assert_called_once()
