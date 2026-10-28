"""Record actual public operations/checkpoints, then explicitly confirm a draft.

A human CLI or an authorized agent may drive this API. No provider is invoked.
Recordings are local task data, never new G2T authority or built-in app rules.
"""
from __future__ import annotations
import copy
import hashlib
import json

from .native import NativeBridgeError, _selection_already_satisfied
from .tui import checked_view, _operation_keys
from .workflow import VERSION, HUMAN_VERSION, validate_workflow, run_workflow, WorkflowBlocked

RECORDING = 'jev.workflow.recording.experimental.v1'
CONFIRMED = 'jev.workflow.confirmed.experimental.v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class RecordingSession:
    """Each human/agent-authored step is performed and checked before recording."""
    def __init__(self, bridge, *, name, goal, actor, literals=(), emit=lambda event: None):
        if actor not in ('human', 'agent'): raise ValueError('Recorder actor must be human or agent')
        self.bridge, self.name, self.goal, self.actor = bridge, name, goal, actor
        self.literals, self.emit = tuple(literals), emit
        self.steps, self.evidence = [], []
        self.uncertain, self.sources = set(), set()
        self.owner = None; self.blocked = False

    def request(self, command, **kwargs):
        response = self.bridge.request(command, **kwargs)
        doc, _, _ = checked_view(response)
        owner = (doc['session'], doc['generation'])
        if self.owner is not None and owner != self.owner:
            raise WorkflowBlocked('Recording owner/generation changed; stop recording')
        self.owner = owner
        return response

    def execute(self, doc, candidate):
        local, source = _operation_keys(doc, candidate, candidate.get('parameter'))
        if local in self.uncertain or source is not None and source in self.sources:
            raise NativeBridgeError({'ok': False, 'delivery': 'not_attempted',
                                     'error': 'Earlier recording action unknown; no replay across recorded steps'})
        try: receipt = self.bridge.execute(doc, candidate)
        except NativeBridgeError as error:
            if error.delivery != 'not_attempted':
                self.uncertain.add(local)
                if source is not None: self.sources.add(source)
            raise
        if (receipt.get('effect') == 'unknown' or receipt.get('accepted') is not True) and not _selection_already_satisfied(receipt, candidate, doc):
            self.uncertain.add(local)
            if source is not None: self.sources.add(source)
        return receipt

    def record_step(self, step, **options):
        if self.blocked: raise WorkflowBlocked('Recording stopped after failure; no automatic continuation')
        recipe = {'version': HUMAN_VERSION if step.get('kind') == 'human' else VERSION, 'name': self.name, 'goal': self.goal,
                  'steps': [copy.deepcopy(step)],
                  'endpoint': {'kind': 'checkpoints_reached', 'reason': 'Recorded step checkpoint only'}}
        validate_workflow(recipe)
        result = run_workflow(recipe, self, literals=self.literals, emit=self.emit, **options)
        self.evidence.append({'step': copy.deepcopy(step), 'result': result})
        if result['status'] == 'checkpoints_reached': self.steps.append(copy.deepcopy(step))
        else: self.blocked = True
        return result

    def draft(self, endpoint):
        if self.blocked: raise WorkflowBlocked('Failed recording cannot be promoted to a complete flow')
        recipe = validate_workflow({'version': HUMAN_VERSION if any(s.get('kind') == 'human' for s in self.steps) else VERSION,
                                    'name': self.name, 'goal': self.goal,
                                    'steps': copy.deepcopy(self.steps), 'endpoint': endpoint})
        return {'version': RECORDING, 'actor': self.actor, 'confirmed': False,
                'recipe': recipe, 'evidence': copy.deepcopy(self.evidence),
                'provider_calls': 0, 'input_tokens': 0, 'output_tokens': 0}


def confirm_recording(draft, *, expected_digest, confirmed_by):
    """Explicit caller review of this exact draft; not identity authentication."""
    if confirmed_by not in ('human', 'agent'): raise ValueError('Confirmation actor must be human or agent')
    if draft.get('version') != RECORDING or draft.get('confirmed') is not False:
        raise ValueError('Expected an unconfirmed actual recording')
    if digest(draft) != expected_digest: raise ValueError('Draft changed since review')
    recipe = validate_workflow(draft['recipe']); evidence = draft['evidence']
    if len(evidence) != len(recipe['steps']): raise ValueError('Recording evidence missing')
    for item, step in zip(evidence, recipe['steps']):
        if (item['step'] != step or item['result'].get('status') != 'checkpoints_reached'
                or item['result'].get('completed_steps') != [step['name']]):
            raise ValueError('Unverified step cannot be confirmed')
        kinds = [e['kind'] for e in item['result']['history']]
        if step.get('kind') == 'human':
            if (kinds.count('human_handoff') != 1 or kinds.count('human_response') != 1
                    or kinds.count('execution_request') or kinds.count('receipt')
                    or kinds.count('checkpoint_passed') != 1
                    or not any(e['kind'] == 'human_response' and e['decision'] == 'resume'
                               for e in item['result']['history'])):
                raise ValueError('Human step needs acknowledgement and fresh public checkpoint, no synthetic receipt')
            continue
        if kinds.count('execution_request') != 1 or kinds.count('receipt') != 1 or kinds.count('checkpoint_passed') != 1:
            raise ValueError('Actual execution and checkpoint evidence required')
    approved = {'version': CONFIRMED, 'confirmed_by': confirmed_by,
                'draft_digest': expected_digest, 'recipe': copy.deepcopy(recipe),
                'evidence_digest': digest(evidence),
                'confirmation_meaning': 'Explicit caller confirmation of a recorded task flow; not authentication, runtime authority or task-success oracle'}
    approved['confirmation_digest'] = digest(approved)
    return approved


def confirmed_recipe(approved):
    if approved.get('version') != CONFIRMED: raise ValueError('Playback requires a confirmed recording')
    expected = approved.get('confirmation_digest')
    if digest({k: v for k, v in approved.items() if k != 'confirmation_digest'}) != expected:
        raise ValueError('Confirmed flow changed; record/review/confirm again')
    return validate_workflow(approved['recipe'])
