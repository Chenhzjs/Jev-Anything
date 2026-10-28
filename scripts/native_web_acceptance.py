#!/usr/bin/env python3
"""Three real browser tasks through one unchanged native adapter and live Jev."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from jev_anything.jev import JevClient
from jev_anything.native import NativeBridge, run


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--image', default='gui2tui-task-tests:local')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--public-web', action='store_true', help='Also test navigation on example.org and Python documentation')
    p.add_argument('--tasks', nargs='+', choices=['preferences','catalog','navigation','example','python'])
    args = p.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    fixture = Path(__file__).resolve().parents[1] / 'docker/native_web_fixture.py'
    tasks = [
        ('preferences', 'http://127.0.0.1:8765/preferences', 'Enable dark mode. Finish when the page reports Dark mode enabled.', []),
        ('catalog', 'http://127.0.0.1:8765/catalog', 'Search the catalog for nebula using the search form, then view the catalog results for nebula.', ['nebula']),
        ('navigation', 'http://127.0.0.1:8765/navigation', 'Open the Installation guide from the documentation index. Finish when Installation instructions are now open is shown.', []),
    ]
    if args.public_web:
        tasks += [
            ('example', 'https://example.org', 'Follow the Learn more link on Example Domain to open the IANA explanation of reserved example domains.', []),
            ('python', 'https://docs.python.org/3/', 'Open the Python Tutorial from the Python documentation home page.', []),
        ]
    if args.tasks:
        tasks = [task for task in tasks if task[0] in args.tasks]
    results = []
    for name, url, goal, texts in tasks:
        container = 'jev-native-' + uuid.uuid4().hex[:10]
        subprocess.run(['docker', 'run', '-d', '--name', container, '--platform', 'linux/amd64', '--shm-size=512m',
                        '-v', f'{args.binary.resolve()}:/gui2tui-agent:ro', '-v', f'{fixture}:/native_web_fixture.py:ro',
                        '--entrypoint', 'dbus-run-session', args.image, '--', 'python3', '/native_web_fixture.py', '--url', url], check=True, capture_output=True)
        bridge = None
        try:
            for _ in range(150):
                if subprocess.run(['docker', 'exec', container, 'test', '-f', '/tmp/native-ready'], capture_output=True).returncode == 0:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Browser startup timed out')
            bridge = NativeBridge(['docker', 'exec', '-i', container, 'python3', '/native_web_fixture.py', '--exec-agent'])
            with (args.output / (name + '.jsonl')).open('x') as log:
                def emit(event):
                    log.write(json.dumps(event, ensure_ascii=False) + '\n')
                    log.flush()
                    print(name, event['kind'], event.get('step', ''), flush=True)
                result = run(goal, bridge, JevClient(), texts=texts, emit=emit)
                emit({'kind': 'result', 'result': result})
            oracle = json.loads(subprocess.check_output(['docker', 'exec', container, 'python3', '/native_web_fixture.py', '--oracle'], text=True))
            requests = json.loads(subprocess.check_output(['docker', 'exec', container, 'python3', '-c',
                'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8765/oracle").read().decode())'], text=True))
            if name == 'preferences':
                confirmed = any(n['role'] == 'check box' and n['name'] == 'Enable dark mode' and n['checked'] for n in oracle)
            elif name == 'catalog':
                confirmed = '/results?q=nebula' in requests and any('Results for: nebula' in (n['text'] or '') for n in oracle)
            elif name == 'navigation':
                confirmed = '/destination' in requests and any('Installation instructions are now open' in (n['text'] or '') for n in oracle)
            elif name == 'example':
                confirmed = any('IANA' in n['name'] and n['role'] == 'document web' for n in oracle)
            else:
                confirmed = any('The Python Tutorial' in n['name'] and n['role'] == 'document web' for n in oracle)
            row = {'task': name, 'goal': goal, 'status': result['status'], 'task_completed': confirmed,
                   'steps': len(result['history']), 'oracle': oracle, 'http_requests': requests}
            (args.output / (name + '-oracle.json')).write_text(json.dumps(row, indent=2))
            results.append({k:v for k,v in row.items() if k not in ('oracle', 'http_requests')})
        finally:
            if bridge:
                bridge.close()
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True)
    summary = {'binary_sha256': hashlib.sha256(args.binary.read_bytes()).hexdigest(),
               'image': subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip(),
               'platform': 'linux/amd64 (emulated on macOS arm64)', 'tasks': results}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if all(r['task_completed'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
