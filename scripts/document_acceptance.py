"""Linux public-AX integration using a deterministic local HTTP stub, no model.

Requires pyatspi and the ordinary GTK fixture supplied by the validation plan.
The application names below are test inputs, never production adapter rules.
"""
import argparse
import collections
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import traceback

import pyatspi
import jev_anything.document
import jev_anything.native
import jev_anything.jev
from jev_anything.jev import JevClient, JevConfig
from jev_anything.native import NativeBridge, NativeBridgeError, run

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,required=True)
parser.add_argument('--fixture',type=Path,required=True)
parser.add_argument('--plan',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();plan=json.loads(args.plan.read_text());out=args.output
out.mkdir(mode=0o700,exist_ok=False);results=[]
(out/'manifest.json').write_text(json.dumps({'plan':plan,'started_at':time.time(),
    'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),
    'fixture_sha256':hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
    'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'jev_source_sha256':{module.__name__:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in [jev_anything.document, jev_anything.native, jev_anything.jev]},
    'provider':'local deterministic HTTP stub; no model inference'},indent=2))
(out/'driver.py').write_bytes(Path(__file__).read_bytes())


def wait_app(pid):
    for _ in range(100):
        for app in pyatspi.Registry.getDesktop(0):
            try:
                if app.get_process_id()==pid:return app
            except Exception:pass
        time.sleep(.1)
    raise RuntimeError(f'No public AX application for {pid}')


def ax_material(app):
    texts=[];names=[];values=[];stack=[app];seen=set()
    while stack:
        node=stack.pop()
        try:
            if str(node.path) in seen:continue
            seen.add(str(node.path))
            if node.getRole()==pyatspi.ROLE_PASSWORD_TEXT:continue
            names.append(node.name)
            try:texts.append(node.queryText().getText(0,-1))
            except NotImplementedError:pass
            try:values.append({'name':node.name,'current':node.queryValue().currentValue})
            except NotImplementedError:pass
            stack.extend(list(node))
        except Exception:continue
    return {'texts':texts,'names':names,'values':values}


class RecordingBridge(NativeBridge):
    def __init__(self,app,scene):
        self.trace=(out/f'{scene}-bridge.jsonl').open('x');self.documents={};self.history=[]
        self.consume_once=scene=='fixture'
        super().__init__([str(args.binary),'--session','desktop','--app',app.name])
    def request(self,command,**fields):
        self.trace.write(json.dumps({'request':{'command':command,**fields}})+'\n');self.trace.flush()
        try:
            response=super().request(command,**fields)
        except NativeBridgeError as error:
            self.trace.write(json.dumps({'response':error.response})+'\n');self.trace.flush();raise
        self.trace.write(json.dumps({'response':response})+'\n');self.trace.flush()
        return response
    def snapshot(self):
        doc=super().snapshot();self.documents[doc['observation_id']]=copy.deepcopy(doc)
        return doc
    def execute(self,doc,candidate):
        if self.consume_once:
            self.consume_once=False
            try:self.request('execute',observation_id=doc['observation_id'],operation_id='deliberately-invalid-validation-id')
            except NativeBridgeError as error:assert error.delivery=='not_attempted'
            else:raise AssertionError('Invalid operation was unexpectedly accepted')
        try:receipt=super().execute(doc,candidate)
        except NativeBridgeError as error:
            self.history.append({'operation':copy.deepcopy(candidate),'receipt':copy.deepcopy(error.response)});raise
        self.history.append({'operation':copy.deepcopy(candidate),'receipt':copy.deepcopy(receipt)})
        return receipt
    def close(self):
        super().close();self.trace.close()


class ProviderStub:
    def __init__(self,scene,bridge,texts=(),values=()):
        self.scene=scene;self.bridge=bridge;self.texts=texts;self.values=values;self.requests=[];self.failures=[]
    def __enter__(self):
        stub=self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));index=len(stub.requests)
                (out/f'{stub.scene}-http-{index}.json').write_bytes(raw)
                try:
                    payload=json.loads(raw);stub.requests.append(payload)
                    doc=payload['state']['accessibility']
                    assert doc==stub.bridge.documents[doc['observation_id']],'Document fields were lost or changed'
                    assert payload['state']['history']==stub.bridge.history,'History/receipt evidence changed'
                    assert b'G2T-P2-SECRET-' not in raw,'Secret reached HTTP'
                    criteria=payload['questions']['action']['criteria'];expected={}
                    for op in doc['operations']:
                        if not op['agent_invocable']:continue
                        options=(stub.texts if op['parameter']=='text' else stub.values) if op.get('parameter') else (None,)
                        for j,literal in enumerate(options):
                            cid=op['id']+f'-p{j}' if op.get('parameter') else op['id']
                            expected[cid]=op
                            view=json.loads(criteria[cid])
                            assert view['operation_id']==op['id']
                            for key,value in op.items():
                                if key=='id':assert view[key]==cid
                                elif key=='parameter':assert view[key]==literal
                                else:assert view[key]==value,(cid,key)
                    assert set(criteria)==set(expected)|{'done','abstain','wait'},'Candidates omitted or extra permissions added'
                    if index >= (2 if stub.scene=='fixture' else 1):choice='done'
                    else:
                        offered=[json.loads(criteria[cid]) for cid in expected]
                        if stub.scene=='fixture':matches=[c for c in offered if c['kind']=='set_value' and c.get('parameter')==35]
                        elif stub.scene=='mousepad':matches=[c for c in offered if c['kind']=='replace_text' and c.get('multiline')]
                        else:matches=[c for c in offered if c['kind']=='action' and c.get('target_label')=='List View']
                        assert len(matches)==1,[(c['id'],c.get('label')) for c in matches]
                        choice=matches[0]['id']
                    body=json.dumps({'id':'local-stub','answers':{'action':{'type':'choice','choice':choice}}}).encode()
                    self.send_response(200)
                except Exception:
                    stub.failures.append(traceback.format_exc());body=b'{"error":"stub input validation failed"}';self.send_response(422)
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=JevClient(JevConfig(api_key='local-stub-only',model='local/stub-validation',
            api_url=f'http://127.0.0.1:{self.server.server_port}/decisions'))
        return self
    def __exit__(self,*exc):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        (out/f'{self.scene}-stub-failures.json').write_text(json.dumps(self.failures,indent=2))


def check_scene(task):
    scene=task['scene']
    if scene=='fixture':command=['python3',str(args.fixture)]
    elif scene=='mousepad':command=['mousepad','--disable-server']
    else:
        initial=out/'initial-files';initial.mkdir()
        for name in ['Report A.txt','Report B.txt','Reference.txt']:(initial/name).write_text('Initial test content before GUI launch.\n')
        command=['thunar',str(initial)]
    proc=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=(out/f'{scene}-gui.log').open('x'))
    bridge=None
    try:
        app=wait_app(proc.pid);bridge=RecordingBridge(app,scene)
        texts=[plan['text']] if scene=='mousepad' else [];values=[35] if scene=='fixture' else []
        events=[]
        with (out/f'{scene}-events.jsonl').open('x') as trace:
            def emit(event):events.append(event);trace.write(json.dumps(event)+'\n');trace.flush()
            with ProviderStub(scene,bridge,texts,values) as stub:
                result=run(task['goal'],bridge,stub.client,texts=texts,values=values,max_steps=task['max_steps'],emit=emit)
                assert not stub.failures,stub.failures
                assert result['status']=='model_completed',result.get('status')
                assert result['task_completed'] is None
                if scene=='fixture':
                    assert len(stub.requests)==3
                    assert result['history'][0]['receipt']['delivery']=='not_attempted'
                    assert result['history'][1]['receipt']['accepted'] is True
                # Independent public read after all writes. No uncertain replay.
                material=ax_material(app);(out/f'{scene}-independent-ax.json').write_text(json.dumps(material,indent=2))
                if scene=='fixture':assert any(v['name']=='Public amount' and v['current']==35 for v in material['values'])
                elif scene=='mousepad':assert plan['text'] in material['texts']
                else:assert {'Report A.txt','Report B.txt'} <= set(material['names'])
                doc=result['observation']
                actual=collections.Counter(p['read']['text'] for p in doc['text_payloads'] if p['read']['status']=='complete')
                assert actual==collections.Counter(material['texts']),'Independent complete public Text inventory differs'
                (out/f'{scene}-result.json').write_text(json.dumps(result,indent=2))
                results.append({'scene':scene,'passed':True,'provider':'local HTTP stub','requests':len(stub.requests),
                    'request_bytes':[len((out/f'{scene}-http-{i}.json').read_bytes()) for i in range(len(stub.requests))],
                    'model_result':result['status'],'model_task_completed':result['task_completed'],
                    'independent_engineering_oracle':True,'operations':len(doc['operations']),
                    'nodes':len(doc['nodes']),'text_sources':len(doc['text_payloads']),
                    'completeness':doc['completeness'],
                    'receipt_truth':[{'accepted':h['receipt'].get('accepted'),'effect':h['receipt'].get('effect'),
                        'delivery':h['receipt'].get('delivery')} for h in result['history']]})
    finally:
        if bridge:bridge.close()
        proc.terminate();proc.wait(timeout=10)


for task in plan['scenes']:
    try:check_scene(task)
    except Exception:
        (out/f"{task['scene']}-failure.txt").write_text(traceback.format_exc())
        results.append({'scene':task['scene'],'passed':False,'error':traceback.format_exc()})
    (out/'results.json').write_text(json.dumps(results,indent=2))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
