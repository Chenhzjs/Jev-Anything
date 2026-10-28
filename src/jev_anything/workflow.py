"""Explicit deterministic task recipes over the existing G2T TUI protocol.

Rust performs all public target searches and organization. No provider is used.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

from .native import NativeBridge, NativeBridgeError, _selection_already_satisfied
from .tui import checked_view, validate_plan, _operation_keys

VERSION = 'jev.workflow.experimental.v1'
HUMAN_VERSION = 'jev.workflow.experimental.v2'
FIND = {'find_action', 'find_control', 'find_command'}


def _object(value, fields, required):
    if not isinstance(value, dict) or set(value) - set(fields) or not set(required) <= set(value):
        raise ValueError('Invalid workflow object fields')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Workflow text must be nonempty')


def _locate(value):
    _object(value, ('action', 'query', 'context', 'exact'), ('action', 'query'))
    if value['action'] not in FIND:
        raise ValueError('Workflow locate requires a public G2T find tool')
    _text(value['query'])
    if value.get('context') is not None: _text(value['context'])
    if type(value.get('exact', False)) is not bool: raise ValueError('Exact must be boolean')


def _checkpoint(after):
    _object(after, ('kind', 'locate', 'reader', 'query'), ('kind',))
    if after['kind'] == 'readback':
        if set(after) != {'kind'}: raise ValueError('Unexpected readback fields')
    elif after['kind'] == 'control':
        if set(after) != {'kind', 'locate'}: raise ValueError('Control checkpoint needs locate')
        _locate(after['locate'])
    elif after['kind'] == 'text':
        if set(after) != {'kind', 'reader', 'query'}: raise ValueError('Text checkpoint needs Reader and query')
        _text(after['query'])
        _object(after['reader'], ('query', 'context', 'exact'), ())
        for key in ('query', 'context'):
            if after['reader'].get(key) is not None: _text(after['reader'][key])
        if type(after['reader'].get('exact', False)) is not bool: raise ValueError('Exact must be boolean')
    else: raise ValueError('Unknown checkpoint kind')


def validate_workflow(recipe):
    _object(recipe, ('version', 'name', 'goal', 'steps', 'endpoint'),
            ('version', 'name', 'goal', 'steps', 'endpoint'))
    if recipe['version'] not in (VERSION, HUMAN_VERSION): raise ValueError('Unsupported workflow version')
    _text(recipe['name']); _text(recipe['goal'])
    steps = recipe['steps']
    if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
        raise ValueError('Workflow requires 1..64 explicit steps')
    for step in steps:
        if not isinstance(step, dict): raise ValueError('Workflow step must be an object')
        if recipe['version'] == HUMAN_VERSION and step.get('kind') == 'human':
            _object(step, ('kind', 'name', 'instructions', 'after'), ('kind', 'name', 'instructions', 'after'))
            _text(step['name']); _text(step['instructions'])
            _checkpoint(step['after'])
            if step['after']['kind'] == 'readback':
                raise ValueError('Human acknowledgement cannot manufacture a primitive receipt')
            continue
        _object(step, ('name', 'locate', 'operation', 'literal_index', 'after'),
                ('name', 'locate', 'operation', 'after'))
        _text(step['name']); _locate(step['locate'])
        op = step['operation']
        _object(op, ('kind', 'name', 'selected', 'increase', 'multiline'), ('kind',))
        kind = op['kind']
        fields = {'action': {'kind', 'name'}, 'replace_text': {'kind'},
                  'selection': {'kind', 'selected'}, 'set_value': {'kind'},
                  'adjust_value': {'kind', 'increase'}}
        if kind not in fields or set(op) != fields[kind]:
            raise ValueError('Operation must specify its exact public kind and discriminator')
        if kind == 'action': _text(op['name'])
        for key in ('selected', 'increase'):
            if key in op and type(op[key]) is not bool: raise ValueError('Operation flag must be boolean')
        index = step.get('literal_index')
        if index is not None and (type(index) is not int or index < 0):
            raise ValueError('Write data must reference a supplied literal')
        _checkpoint(step['after'])
    _object(recipe['endpoint'], ('kind', 'reason'), ('kind', 'reason'))
    if recipe['endpoint']['kind'] not in ('pause', 'checkpoints_reached'):
        raise ValueError('Endpoint cannot assert independent task completion')
    _text(recipe['endpoint']['reason'])
    return recipe


class WorkflowBlocked(RuntimeError):
    pass


def run_workflow(recipe, bridge, *, literals=(), max_observations=4, poll_seconds=.25,
                 width=120, height=40, emit=lambda event: None, human_handler=None):
    """No retries of writes, fallback planner, cached IDs or implicit completion."""
    validate_workflow(recipe)
    if type(max_observations) is not int or not 1 <= max_observations <= 32:
        raise ValueError('Checkpoint observation limit must be 1..32')
    if not isinstance(poll_seconds, (int, float)) or not 0 <= poll_seconds <= 5:
        raise ValueError('Invalid read-only poll interval')
    history, completed, uncertain, sources = [], [], set(), set()
    response = None; owner = None; attempted = False; step_name = None

    def record(kind, **data):
        event = {'kind': kind, 'step': step_name, **data}
        history.append(event); emit(event)

    def accept(value):
        nonlocal response, owner
        doc, _, _ = checked_view(value)
        current = (doc['session'], doc['generation'])
        if owner is not None and current != owner:
            raise WorkflowBlocked('Runtime owner/generation changed; no rebinding or continuation')
        owner = current; response = value
        return doc

    def observe():
        value = bridge.request('observe_tui_text', width=width, height=height)
        accept(value); record('observation', response=value)

    def navigate(action, **data):
        plan = {'kind': 'navigate', 'action': action, **data}
        validate_plan(plan, response, literals)
        value = bridge.request('tui_navigate', observation_id=response['observation']['observation_id'],
                               action=action, query=data.get('query'), context=data.get('context'),
                               exact=data.get('exact', False), max_steps=64, width=width, height=height)
        accept(value)
        nav = value['navigation']
        if nav.get('gui_write') is not False or nav.get('activation') != 'not_attempted':
            raise WorkflowBlocked('Invalid read-only navigation receipt')
        record('navigation', plan=plan, response=value)
        return nav

    def locate(selector):
        nav = navigate(**selector)
        if nav.get('status') == 'ambiguous':
            raise WorkflowBlocked('Public target is ambiguous; no order/ID tie-break')
        if nav.get('status') != 'focused' or nav.get('selection_confirmed') is not True:
            return None
        return nav.get('target')

    def checkpoint(check, receipt, candidate, before):
        if check['kind'] == 'readback':
            return receipt.get('effect') == 'confirmed' or _selection_already_satisfied(receipt, candidate, before)
        if check['kind'] == 'control': return locate(check['locate']) is not None
        nav = navigate('open_reader', **check['reader'])
        if nav.get('status') == 'ambiguous':
            raise WorkflowBlocked('Public Reader root is ambiguous')
        if nav.get('status') != 'opened': return False
        nav = navigate('find_text', query=check['query'])
        return nav.get('status') == 'searched' and type(nav.get('matches')) is int and nav['matches'] > 0

    def result(status, reason):
        return {'version': recipe['version'], 'workflow': recipe['name'], 'status': status,
                'reason': reason, 'task_completed': None, 'completed_steps': completed,
                'blocked_step': step_name if status not in ('pause', 'checkpoints_reached') else None,
                'provider_calls': 0, 'input_tokens': 0, 'output_tokens': 0,
                'history': history}

    try:
        # Validate all literal bindings before making any GUI write.
        for step in recipe['steps']:
            index = step.get('literal_index')
            if index is not None and index >= len(literals): raise WorkflowBlocked('Missing user literal')
        for step in recipe['steps']:
            step_name = step['name']; observe()
            if step.get('kind') == 'human':
                record('human_handoff', instructions=step['instructions'],
                       automatic_GUI_writes=False, images_sent_to_model=False)
                if human_handler is None:
                    return result('needs_human', 'Original GUI interaction required; no handler configured')
                decision = human_handler({'step': step_name, 'instructions': step['instructions']})
                if decision not in ('resume', 'cancel'):
                    raise WorkflowBlocked('Invalid human response; no automatic continuation')
                record('human_response', decision=decision,
                       meaning='Human acknowledgement only; not task completion or a GUI receipt')
                if decision == 'cancel': return result('cancelled', 'User cancelled original GUI handoff')
                # Retire every pre-handoff operation ID before any further decision.
                for attempt in range(max_observations):
                    observe()
                    if checkpoint(step['after'], None, None, None): break
                    record('checkpoint_pending', attempt=attempt + 1, check=step['after'])
                    if attempt + 1 == max_observations:
                        raise WorkflowBlocked('Public state after human interaction does not establish the checkpoint')
                    if poll_seconds: time.sleep(poll_seconds)
                completed.append(step_name)
                record('checkpoint_passed', check=step['after'], human_step=True,
                       meaning='Fresh public predicate only; not task completion')
                continue
            target = locate(step['locate'])
            if target is None: raise WorkflowBlocked('Required current public target is unavailable')
            doc, _, visible = checked_view(response)
            node = next(n for n in doc['nodes'] if n['id'] == target)
            if node.get('redacted') or node.get('text_input_kind') == 'Password':
                raise WorkflowBlocked('Protected target cannot be recorded or executed')
            matches = [op for op in visible.values() if op['target'] == target
                       and all(op.get(k) == v for k, v in step['operation'].items())]
            if len(matches) != 1:
                raise WorkflowBlocked('Exact operation is unavailable or ambiguous on the G2T-selected target')
            op = matches[0]; plan = {'kind': 'execute', 'operation_id': op['id'],
                                    'literal_index': step.get('literal_index')}
            validate_plan(plan, response, literals)
            parameter = literals[plan['literal_index']] if plan['literal_index'] is not None else None
            local, source = _operation_keys(doc, op, parameter)
            if local in uncertain or source is not None and source in sources:
                raise WorkflowBlocked('Earlier unknown effect; operation not replayed')
            candidate = {**op, 'operation_id': op['id']}
            if parameter is not None: candidate['parameter'] = parameter
            record('execution_request', observation_id=doc['observation_id'], plan=plan,
                   operation=op, parameter=parameter)
            attempted = True
            try:
                receipt = bridge.execute(doc, candidate)
            except NativeBridgeError as error:
                record('operation_error', response=error.response)
                # A rejection still gets a fresh observation, but never a write retry.
                if error.delivery == 'not_attempted':
                    attempted = False; observe()
                    return result('blocked', 'G2T rejected before delivery; fresh observation recorded, no automatic retry')
                return result('unknown', 'Delivery unknown; no replay or further GUI writes')
            record('receipt', receipt=receipt); attempted = False
            already = _selection_already_satisfied(receipt, candidate, doc)
            if not already and receipt.get('accepted') is not True:
                observe(); return result('unknown', 'Backend acceptance not established; no replay')
            if receipt.get('effect') == 'unknown':
                uncertain.add(local)
                if source is not None: sources.add(source)
            # Fresh public facts are required even after a confirmed primitive.
            for attempt in range(max_observations):
                observe()
                if checkpoint(step['after'], receipt, candidate, doc): break
                record('checkpoint_pending', attempt=attempt + 1, check=step['after'])
                if attempt + 1 == max_observations:
                    raise WorkflowBlocked('Declared public checkpoint not established; no write replay')
                if poll_seconds: time.sleep(poll_seconds)
            completed.append(step_name); record('checkpoint_passed', check=step['after'],
                                                meaning='Declared public predicate only; not task completion')
        return result(recipe['endpoint']['kind'], recipe['endpoint']['reason'])
    except NativeBridgeError as error:
        record('bridge_error', response=error.response)
        return result('unknown' if attempted or error.delivery != 'not_attempted' else 'blocked', str(error))
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        return result('unknown' if attempted else 'blocked', str(error))


def main():
    from .workflow_recording import RecordingSession, confirm_recording, confirmed_recipe, digest
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    record = commands.add_parser('record', help='Human/agent supplies steps interactively; record actual effects/checkpoints')
    record.add_argument('--name', required=True); record.add_argument('--goal', required=True)
    record.add_argument('--actor', choices=('human', 'agent'), required=True)
    record.add_argument('--draft', required=True)
    play = commands.add_parser('play', help='Replay an explicitly confirmed recording; no model')
    play.add_argument('--workflow', required=True)
    for command in (record, play):
        command.add_argument('--allow-human', action='store_true', help='Wait for explicit terminal acknowledgement at a recorded human step')
        command.add_argument('--human-view-url', help='Configured original desktop viewer; not stored in task history')
        command.add_argument('--human-view-file', help='Private viewer access file for the human; contents never read by this client')
        command.add_argument('--text', action='append', default=[])
        command.add_argument('--value', action='append', type=float, default=[])
        command.add_argument('--max-observations', type=int, default=4)
        command.add_argument('--trace', required=True, help='New private evidence file; never overwritten')
        command.add_argument('--bridge', nargs=argparse.REMAINDER, required=True)
    confirm = commands.add_parser('confirm', help='Confirm the exact reviewed draft; does not execute GUI operations')
    confirm.add_argument('--draft', required=True); confirm.add_argument('--draft-digest', required=True)
    confirm.add_argument('--confirmed-by', choices=('human', 'agent'), required=True)
    confirm.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.mode == 'confirm':
        approved = confirm_recording(json.loads(Path(args.draft).read_text()),
                                     expected_digest=args.draft_digest, confirmed_by=args.confirmed_by)
        with open(args.output, 'x') as output: json.dump(approved, output, ensure_ascii=False, indent=2)
        print(json.dumps({'status': 'confirmed', 'workflow': args.output, 'provider_calls': 0}))
        return
    if args.mode == 'record' and Path(args.draft).exists():
        raise FileExistsError('Recording draft already exists; choose a new evidence path')
    recipe = confirmed_recipe(json.loads(Path(args.workflow).read_text())) if args.mode == 'play' else None
    with open(args.trace, 'x') as trace:
        def emit(event):
            trace.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n'); trace.flush()
        emit({'kind': 'workflow_start', 'mode': args.mode, 'recipe': recipe, 'provider_calls': 0,
              'max_observations': args.max_observations})
        bridge = NativeBridge(args.bridge, timeout=180)
        try:
            from .human import terminal_handler
            handler = terminal_handler(args.human_view_url, access_file=args.human_view_file) if args.allow_human else None
            if args.mode == 'play':
                outcome = run_workflow(recipe, bridge, literals=args.text + args.value,
                                       max_observations=args.max_observations, emit=emit, human_handler=handler)
            else:
                import sys
                session = RecordingSession(bridge, name=args.name, goal=args.goal, actor=args.actor,
                                           literals=args.text + args.value, emit=emit)
                response = session.request('observe_tui_text', width=120, height=40)
                emit({'kind': 'recording_observation', 'response': response})
                print(json.dumps({'tui_view': response['tui_view']}, ensure_ascii=False), flush=True)
                outcome = {'status': 'recording_not_finished', 'provider_calls': 0}
                for line in sys.stdin:
                    command = json.loads(line)
                    if command.get('kind') == 'finish':
                        draft = session.draft(command['endpoint'])
                        with open(args.draft, 'x') as output: json.dump(draft, output, ensure_ascii=False, indent=2)
                        outcome = {'status': 'draft_requires_confirmation', 'draft': args.draft,
                                   'draft_digest': digest(draft), 'provider_calls': 0}
                        break
                    if command.get('kind') == 'step':
                        outcome = session.record_step(command['step'], max_observations=args.max_observations,
                                                      human_handler=handler)
                        print(json.dumps({k: v for k, v in outcome.items() if k != 'history'}, ensure_ascii=False), flush=True)
                        if outcome['status'] != 'checkpoints_reached': break
                        response = session.request('observe_tui_text', width=120, height=40)
                    elif command.get('kind') == 'observe':
                        response = session.request('observe_tui_text', width=120, height=40)
                    else:
                        validate_plan(command, response, args.text + args.value)
                        if command['kind'] != 'navigate': raise ValueError('Use a step with a checkpoint to record GUI execution')
                        response = session.request('tui_navigate', observation_id=response['observation']['observation_id'],
                                                   action=command['action'], query=command.get('query'),
                                                   context=command.get('context'), exact=command.get('exact', False),
                                                   max_steps=64, width=120, height=40)
                    emit({'kind': 'recording_observation', 'response': response})
                    print(json.dumps({'tui_view': response['tui_view']}, ensure_ascii=False), flush=True)
                else:
                    outcome = {'status': 'recording_not_finished', 'provider_calls': 0,
                               'reason': 'No finish command; complete trace retained, no confirmed flow created'}
        finally: bridge.close()
        emit({'kind': 'workflow_result', 'result': outcome})
        print(json.dumps({k: v for k, v in outcome.items() if k != 'history'}, ensure_ascii=False))
    if outcome['status'] not in ('pause', 'checkpoints_reached', 'draft_requires_confirmation'): raise SystemExit(2)


if __name__ == '__main__': main()
