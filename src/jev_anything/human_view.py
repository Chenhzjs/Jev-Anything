"""Opt-in Docker X11 desktop viewer for a human, separate from G2T semantics.

Requires installed x11vnc/noVNC/websockify and a loopback-published 6080 port.
No desktop is created, no pixels are inspected, and no input is synthesized.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
from urllib.parse import quote


START = r'''
import json,os,pathlib,subprocess,sys,tempfile,time
config=json.loads(sys.stdin.read(4096))
root=pathlib.Path(tempfile.mkdtemp(prefix='g2t-human-view-'))
os.chmod(root,0o700)
tokenfile=root/'tokens'
tokenfile.write_text(config['token']+': 127.0.0.1:5901'+chr(10));os.chmod(tokenfile,0o600)
processes=[]
def stamp(pid):return pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
try:
 for argv in [
  ['x11vnc','-display',config['display'],'-rfbport','5901','-localhost','-shared','-forever','-nopw','-quiet'],
  ['websockify','--web','/usr/share/novnc','--token-plugin','TokenFile','--token-source',str(tokenfile),'0.0.0.0:6080']]:
  p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  processes.append({'pid':p.pid,'stamp':stamp(p.pid)})
  time.sleep(.2)
  if p.poll() is not None:raise RuntimeError('Human viewer process did not start')
 (root/'processes.json').write_text(json.dumps(processes))
 os.chmod(root/'processes.json',0o600)
 print(json.dumps({'remote_state':str(root)}))
except Exception:
 for item in reversed(processes):
  try:os.kill(item['pid'],15)
  except ProcessLookupError:pass
 raise
'''

STOP = r'''
import json,os,pathlib,sys
root=pathlib.Path(sys.argv[1])
if root.parent!=pathlib.Path('/tmp') or not root.name.startswith('g2t-human-view-') or root.is_symlink():raise RuntimeError('Invalid viewer state')
if root.stat().st_uid!=os.getuid():raise RuntimeError('Viewer owner mismatch')
for item in reversed(json.loads((root/'processes.json').read_text())):
 try:
  current=pathlib.Path('/proc/'+str(item['pid'])+'/stat').read_text().rsplit(')',1)[1].split()[19]
  if current==item['stamp']:os.kill(item['pid'],15)
 except FileNotFoundError:pass
# Revoke only this viewer's credential; GUI, profile and evidence are untouched.
(root/'tokens').unlink(missing_ok=True)
print(json.dumps({'closed':True}))
'''


def _run(argv, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30, **kwargs)
    if result.returncode: raise RuntimeError('Human viewer command failed; check installed dependencies and display/port ownership')
    return result.stdout


def start_viewer(container, display, *, user):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', container): raise ValueError('Invalid container name')
    if not re.fullmatch(r':[0-9]{1,4}(?:\.[0-9]+)?', display): raise ValueError('Explicit X11 display required')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:-]{0,63}',user):raise ValueError('Explicit GUI session user required')
    info = json.loads(_run(['docker','inspect',container]))[0]
    ports = info['NetworkSettings']['Ports'].get('6080/tcp') or []
    if len(ports) != 1 or ports[0]['HostIp'] != '127.0.0.1':
        raise ValueError('Viewer requires exactly one 127.0.0.1 host binding for container port 6080')
    # Per-user fresh private state, outside task traces and GUI source artifacts.
    state = Path(tempfile.mkdtemp(prefix='g2t-human-access-'));os.chmod(state,0o700)
    token = secrets.token_urlsafe(32)
    remote = json.loads(_run(['docker','exec','--user',user,'-i',container,'python3','-c',START],
                             input=json.dumps({'token':token,'display':display})))
    url = 'http://127.0.0.1:'+ports[0]['HostPort']+'/vnc.html#autoconnect=1&resize=scale&path='+quote('websockify?token='+token,safe='')
    access = state/'OPEN-DESKTOP.txt'
    fd = os.open(access,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write('仅供用户打开原桌面；链接含临时访问凭证，请勿粘贴到模型或日志。\n\n'+url+'\n')
    metadata = {'container':container,'display':display,'user':user,'remote_state':remote['remote_state'],
                'access_file':str(access),'base_url':'http://127.0.0.1:'+ports[0]['HostPort'],
                'transport':'human-only noVNC','pixels_read_by_agent':False}
    path = state/'viewer-state.json'
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(metadata,stream,indent=2)
    return path


def stop_viewer(state_file):
    metadata = json.loads(Path(state_file).read_text())
    container = metadata['container']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',container):raise ValueError('Invalid container name')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:-]{0,63}',metadata['user']):raise ValueError('Invalid viewer owner')
    return json.loads(_run(['docker','exec','--user',metadata['user'],container,'python3','-c',STOP,metadata['remote_state']]))


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='mode',required=True)
    start=commands.add_parser('start');start.add_argument('--container',required=True);start.add_argument('--display',required=True)
    start.add_argument('--user',required=True,help='Same user/UID as the existing GUI session')
    stop=commands.add_parser('stop');stop.add_argument('--state',required=True)
    args=parser.parse_args()
    if args.mode=='start':
        state=start_viewer(args.container,args.display,user=args.user)
        # Only file paths are printed; access tokens never enter stdout/task history.
        metadata=json.loads(state.read_text());print(json.dumps({'state_file':str(state),'access_file':metadata['access_file']}))
    else:print(json.dumps(stop_viewer(args.state)))


if __name__=='__main__':main()
