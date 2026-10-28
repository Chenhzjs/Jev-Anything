"""Mechanical packet encoding checks; not GUI or model success evidence."""
import copy
import json
import unittest

from jev_anything.chunked import ChunkError
from jev_anything.record_wire import checked_pack, unpack


class RecordWireTests(unittest.TestCase):
    def test_typed_unknown_fields_order_unicode_and_literal_tags_roundtrip(self):
        original=[{'id':'r0','path':'/future/a~1b','kind':'value','value':
                   {'schemas':[True,1,1.0,-0.0,None,{},[]],'@':['reserved',{'data':'尾🙂'*100}],
                    'literal_json':'{"not":"parsed"}','':''}},
                  {'id':'r1','path':'/future/z','kind':'value','value':False}]
        before=copy.deepcopy(original);packet=checked_pack(original)
        self.assertEqual(json.dumps(unpack(packet)),json.dumps(original))
        self.assertEqual(original,before)
        for broken in [{'encoding':packet['encoding'],'schemas':[],'data':[0,[99,'missing']]},
                       {'encoding':packet['encoding'],'schemas':[['x']],'data':[0,[1,1,2]]},
                       {'encoding':packet['encoding'],'schemas':[['x','x']],'data':[0]},
                       {'encoding':packet['encoding'],'schemas':[],'data':[False]},
                       {'encoding':packet['encoding'],'schemas':[],'data':[0,[-1,0]],'shared':[]},
                       {'encoding':packet['encoding'],'schemas':[],'data':[0,[-1,0]],'shared':[[-1,0]]}]:
            with self.assertRaises(ChunkError):unpack(broken)

    def test_repeated_field_names_are_compact_without_dropping_rows(self):
        rows=[{'id':f'r{i}','path':f'/nodes/{i}','kind':'value','value':
               {'id':i,'parent':1,'role':'TextInput','label':None,'states':['Enabled','Editable'],
                'description':'public','unknown_future_field':{'typed':1.0}}} for i in range(100)]
        wire=checked_pack(rows)
        encode=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
        self.assertLess(len(encode(wire)),len(encode(rows)))
        self.assertEqual(encode(unpack(wire)),encode(rows))
        repeated=[{'public_text':'完整重复正文🙂'*40} for _ in range(5)]
        pooled=checked_pack(repeated)
        self.assertTrue(pooled['shared'])
        self.assertEqual(encode(unpack(pooled)),encode(repeated))
        self.assertEqual(wire['record_ids_start'],0)
        prefixed=checked_pack([{'id':f'r{90+i}','path':f'/long-public-source-prefix/nodes/{i}',
                              'value':{'id':f'r{i}','path':'/payload/literal'}} for i in range(20)])
        self.assertTrue(prefixed['path_prefixes'])
        self.assertEqual(prefixed['record_ids_start'],90)
        for key,value in [('record_ids_start',True),('record_ids_start',-1),('path_prefixes',[])]:
            broken=copy.deepcopy(prefixed);broken[key]=value
            with self.assertRaises(ChunkError):unpack(broken)
        unordered=[{'id':'r05','path':'/a'},{'path':'/b','id':'r6'}]
        self.assertNotIn('record_ids_start',checked_pack(unordered))
        self.assertEqual(unpack(checked_pack(unordered)),unordered)
        short='ordinary short public content'
        short_packet=checked_pack([{'value':short} for _ in range(4)])
        self.assertFalse(short_packet['shared'])
        self.assertIn(short,json.dumps(short_packet['data']))
