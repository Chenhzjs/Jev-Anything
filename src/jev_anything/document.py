"""Thin reader for G2T's shared document, never a semantic organizer.

G2T owns privacy, source closure, organization and invocation authority. Keep
the complete wire object, including unknown additive fields, in model state.
"""

import json

DOCUMENT_VERSION = "gui2tui.agent.document.v1"
SOURCE_IDENTITY_VERSION = "gui2tui.source_locator_refs.v1"


def is_document(observation):
    version = observation.get("version")
    if version in (None, "gui2tui.agent.v1"):
        return False
    if version != DOCUMENT_VERSION:
        raise ValueError(f"Unsupported G2T observation version: {version}")
    return True


def read_document(observation):
    """Check the versioned envelope and pass every field through unchanged.

    This is not a second source-inventory validator. In particular, partial or
    unavailable AX material does not revoke other advertised operations.
    """
    if not is_document(observation):
        raise ValueError("Expected a complete-document protocol response")
    for key in ("observation_id", "session", "generation", "collection",
                "readable_scope", "interaction_scope", "completeness",
                "execution_authority", "shared_organization_policy", "regions", "commands"):
        if key not in observation:
            raise ValueError(f"Document envelope is missing {key}")
    for key in ("nodes", "operations", "relations", "text_payloads", "content",
                "choices", "scopes", "sources",
                "boundary_references", "value_domains", "document_probes"):
        if not isinstance(observation.get(key), list):
            raise ValueError(f"Document envelope requires the {key} array")
    # A redacted record is not part of this protocol's public source inventory.
    # Reject an incompatible producer instead of trying to sanitize its joins.
    if any(node.get("redacted") for node in observation["nodes"]):
        raise ValueError("Document producer exported a redacted source")
    return observation


def invocable_operations(observation):
    document = read_document(observation)
    for operation in document["operations"]:
        if not isinstance(operation.get("agent_invocable"), bool):
            raise ValueError("Document operation is missing agent_invocable")
        if operation["agent_invocable"]:
            yield operation


def public_focus_selection(observation):
    """Copy current public state flags for recurring request metadata.

    This is a wire projection of Rust-owned facts, not grouping, task inference
    or a claim about unexposed nodes. Full source material remains unchanged.
    """
    document = read_document(observation)
    selection_targets = {op['target'] for op in document['operations'] if op['kind'] == 'selection'}
    rows = []
    for node in document['nodes']:
        flags = [state for state in node.get('states', []) if state in ('Selected', 'Focused')]
        if node['id'] not in selection_targets and not flags:
            continue
        rows.append({'source': node['id'], 'parent': node.get('parent'), 'role': node['role'],
                     'label': node.get('label'), 'observed_state_flags': flags,
                     'source_partial': node.get('partial', True)})
    return {'version': 'jev.public-focus-selection.v1',
            **{key: document[key] for key in ('session', 'generation', 'observation_id',
                                            'interaction_scope', 'readable_scope')},
            'nodes': rows, 'is_execution_authority': False,
            'coverage': 'Observed flags of public selection-operation targets and selected/focused nodes; whole application not claimed'}


def _expand_column(column):
    kind = column['encoding']; values = column['values']
    if kind == 'numeric_string_runs':
        result = []
        for segment in values:
            if segment[0] == 'literal':
                result.extend(segment[1])
            elif segment[0] == 'numbers':
                _, prefix, suffix, first, step, count, width = segment
                if any(type(v) is not int for v in (first, step, count, width)) or count < 1 or width < 0:
                    raise ValueError('Invalid public string run')
                result.extend(prefix + str(first + step*i).zfill(width) + suffix for i in range(count))
            else:
                raise ValueError('Unknown public string segment')
        return result
    if kind == 'run_columns':
        items, counts = [_expand_column(v) for v in values]
        if len(items) != len(counts) or any(type(n) is not int or n < 1 for n in counts):
            raise ValueError('Invalid public run columns')
        return [v for v, count in zip(items, counts) for _ in range(count)]
    if kind == 'default_positions':
        count = column['length']
        if type(count) is not int or count < 0:
            raise ValueError('Invalid public column length')
        result = [column['default']] * count
        assigned = set()
        for value, positions in values:
            for index in _expand_column(positions):
                if type(index) is not int or index < 0 or index >= count or index in assigned:
                    raise ValueError('Invalid public column position')
                result[index] = value
                assigned.add(index)
        return result
    if kind == 'literal': return list(values)
    if kind == 'runs': return [value for value, count in values for _ in range(count)]
    if kind == 'pattern_runs': return [value for pattern, count in values for _ in range(count) for value in pattern]
    if kind == 'integer_runs':
        return [first + step*i if step else first for first, step, count in values for i in range(count)]
    raise ValueError('Unknown public column encoding')


def _compact_column(values):
    literal = {'encoding': 'literal', 'values': values}
    runs = []
    for value in values:
        if not runs or type(runs[-1][0]) is not type(value) or runs[-1][0] != value: runs.append([value, 1])
        else: runs[-1][1] += 1
    arithmetic = []; i = 0
    while i < len(values):
        first = values[i]; step = 0; count = 1
        if i+1 < len(values) and type(first) is int and type(values[i+1]) is int:
            step = values[i+1]-first; count = 2
            while i+count < len(values) and type(values[i+count]) is int and values[i+count] == first+step*count:
                count += 1
        arithmetic.append([first, step, count]); i += count
    patterns = []; i = 0
    typed = [(type(v).__name__, v) for v in values]
    while i < len(values):
        width = 1; count = 1
        for candidate_width in range(2, min(8, (len(values)-i)//3)+1):
            candidate_count = 1; pattern = typed[i:i+candidate_width]
            while typed[i+candidate_count*candidate_width:i+(candidate_count+1)*candidate_width] == pattern:
                candidate_count += 1
            if candidate_count >= 3 and candidate_width*candidate_count > width*count:
                width = candidate_width; count = candidate_count
        if width == 1 and patterns and patterns[-1][1] == 1:
            patterns[-1][0].append(values[i])
        else: patterns.append([values[i:i+width], count])
        i += width*count
    options = [literal, {'encoding': 'runs', 'values': runs}, {'encoding': 'integer_runs', 'values': arithmetic},
               {'encoding': 'pattern_runs', 'values': patterns}]
    result = min(options, key=lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()))
    if json.dumps(_expand_column(result), ensure_ascii=False) != json.dumps(values, ensure_ascii=False):
        raise ValueError('Public columns changed literal values')
    return result


def _compact_column_v2(values, depth=2):
    """Additional reversible encodings; legacy writers keep their exact wire format."""
    import re
    from collections import Counter
    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())
    options = [_compact_column(values)]
    if depth and values:
        def parts(value):
            match = re.fullmatch(r'(.*?)([0-9]{1,18})([^0-9].*)?', value, re.DOTALL) if type(value) is str else None
            if not match:
                return None
            prefix, digits, suffix = match.groups()
            return prefix, suffix or '', int(digits), len(digits) if digits.startswith('0') and len(digits) > 1 else 0
        strings = []; i = 0
        while i < len(values):
            first = parts(values[i]); count = 1; step = 0
            if first and i+1 < len(values):
                second = parts(values[i+1])
                if second and (first[0], first[1], first[3]) == (second[0], second[1], second[3]):
                    step = second[2]-first[2]; count = 2
                    while i+count < len(values):
                        nxt = parts(values[i+count])
                        if not nxt or (nxt[0], nxt[1], nxt[3]) != (first[0], first[1], first[3]) or nxt[2] != first[2]+step*count:
                            break
                        count += 1
            if count >= 3:
                strings.append(['numbers', first[0], first[1], first[2], step, count, first[3]])
                i += count
            else:
                if not strings or strings[-1][0] != 'literal':
                    strings.append(['literal', []])
                strings[-1][1].append(values[i]); i += 1
        options.append({'encoding': 'numeric_string_runs', 'values': strings})
        runs = []
        for value in values:
            if runs and type(value) is type(runs[-1][0]) and value == runs[-1][0]:
                runs[-1][1] += 1
            else:
                runs.append([value, 1])
        if len(runs) < len(values):
            options.append({'encoding': 'run_columns', 'values': [
                _compact_column_v2([r[0] for r in runs], depth-1),
                _compact_column_v2([r[1] for r in runs], depth-1)]})
        keys = [(type(v).__name__, json.dumps(v, ensure_ascii=False, separators=(',', ':'))) for v in values]
        counts = Counter(keys)
        if 1 < len(counts) <= 8:
            default = counts.most_common(1)[0][0]
            options.append({'encoding': 'default_positions', 'length': len(values),
                'default': values[keys.index(default)], 'values': [
                    [values[keys.index(k)], _compact_column_v2([i for i, key in enumerate(keys) if key == k], depth-1)]
                    for k in counts if k != default]})
    wire = min(options, key=size)
    if json.dumps(_expand_column(wire), ensure_ascii=False) != json.dumps(values, ensure_ascii=False):
        raise ValueError('Public columns changed literal values')
    return wire


def focus_selection_wire(observation, encoding='objects'):
    """Lossless inline columns, avoiding repeated per-node field names."""
    projection = public_focus_selection(observation)
    if encoding == 'objects':
        return projection
    if encoding not in ('columns', 'compact_columns', 'complete_columns'):
        raise ValueError('Unknown focus/selection wire encoding')
    fields = ['source', 'parent', 'role', 'label', 'observed_state_flags', 'source_partial']
    if any(set(row) != set(fields) for row in projection['nodes']):
        raise ValueError('Focus/selection columns would omit a projected field')
    columns = fields[:4]
    symbols = {key: [] for key in columns[2:]}
    indexes = {key: {} for key in symbols}; runs = []
    for node in projection['nodes']:
        row = [node['source'], node['parent']]
        for key in symbols:
            value = node[key]; encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            if encoded not in indexes[key]:
                indexes[key][encoded] = len(symbols[key]); symbols[key].append(value)
            row.append(indexes[key][encoded])
        flags = node['observed_state_flags']; partial = node['source_partial']
        if not runs or runs[-1]['observed_state_flags'] != flags or runs[-1]['source_partial'] != partial:
            runs.append({'observed_state_flags': flags, 'source_partial': partial, 'rows': []})
        runs[-1]['rows'].append(row)
    wire = {**projection, 'version': 'jev.public-focus-selection.v4', 'node_columns': columns,
            'node_symbols': symbols, 'nodes': runs}
    if encoding == 'columns': return wire
    compact_runs = []
    for run in runs:
        values = [_compact_column(list(column)) for column in zip(*run['rows'])]
        restored = [list(row) for row in zip(*[_expand_column(column) for column in values])]
        if restored != run['rows']: raise ValueError('Public state columns changed row order or values')
        compact_runs.append({k:v for k,v in run.items() if k != 'rows'} | {'column_values': values})
    compact = {**wire, 'version': 'jev.public-focus-selection.v5', 'nodes': compact_runs}
    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())
    previous = compact if size(compact)+512 < size(wire) else wire
    if encoding != 'complete_columns':
        return previous
    # State changes fragment grouped runs. Transpose every original row once,
    # including its flags and partial marker, instead of repeating run headers.
    symbols = {**symbols, 'observed_state_flags': []}
    flags_indexes = {}; complete_rows = []
    for run in runs:
        key = json.dumps(run['observed_state_flags'], ensure_ascii=False)
        if key not in flags_indexes:
            flags_indexes[key] = len(symbols['observed_state_flags'])
            symbols['observed_state_flags'].append(run['observed_state_flags'])
        complete_rows.extend(row + [flags_indexes[key], run['source_partial']] for row in run['rows'])
    if not complete_rows:
        return previous
    complete = {**wire, 'version': 'jev.public-focus-selection.v6', 'node_columns': fields,
                'node_symbols': symbols, 'nodes': {'column_values': [
                    _compact_column_v2(list(column)) for column in zip(*complete_rows)]}}
    if expand_focus_selection(complete) != projection:
        raise ValueError('Public state columns changed rows or flags')
    return complete if size(complete)+512 < size(previous) else previous


def expand_focus_selection(wire):
    """Inverse wire codec, with all original source references and typed values."""
    if wire['version'] == 'jev.public-focus-selection.v6':
        columns = [_expand_column(c) for c in wire['nodes']['column_values']]
        if len(columns) != len(wire['node_columns']) or any(len(c) != len(columns[0]) for c in columns):
            raise ValueError('Invalid public state columns')
        rows = [{field: wire['node_symbols'][field][value] if field in wire['node_symbols'] else value
                 for field, value in zip(wire['node_columns'], row)} for row in zip(*columns)]
    else:
        rows = []
        for run in wire['nodes']:
            values = run.get('rows')
            if values is None:
                values = zip(*[_expand_column(c) for c in run['column_values']])
            for row in values:
                rows.append({**{field: wire['node_symbols'][field][value] if field in wire['node_symbols'] else value
                                for field, value in zip(wire['node_columns'], row)},
                             'observed_state_flags': run['observed_state_flags'], 'source_partial': run['source_partial']})
    result = {key:value for key,value in wire.items() if key not in ('node_columns', 'node_symbols')}
    result.update(version='jev.public-focus-selection.v1', nodes=rows)
    return result


def state_facts(observation):
    """Exclude volatile acquisition diagnostics, retaining GUI facts/authority.

    A new observation or duration alone cannot establish a changed consequence
    of an uncertain operation. Neither can it authorize replay.
    """
    read_document(observation)
    facts = {k: v for k, v in observation.items()
             if k not in ("observation_id", "timings")}
    facts["collection"] = {k: v for k, v in observation["collection"].items()
                           if k not in ("started_at_ms", "finished_at_ms")}
    annotations = observation.get("decision_annotations")
    if isinstance(annotations, dict) and annotations.get("version") in ("tui.decision_annotations.v1", "tui.decision_annotations.v2"):
        facts["decision_annotations"] = {k: v for k, v in annotations.items()
                                         if k != "observation_id"}
    return facts


def _source_identity_index(document):
    component = document.get('source_identity')
    if not isinstance(component, dict) or component.get('version') != SOURCE_IDENTITY_VERSION:
        return None
    namespace = component.get('namespace')
    if (not isinstance(namespace, dict) or type(document.get('session')) is not str
            or not document['session'] or type(document.get('generation')) is not int
            or document['generation'] < 1
            or any(type(namespace.get(k)) is not type(document[k]) or namespace.get(k) != document[k]
                   for k in ('session', 'generation'))):
        return None
    result = {}; seen = set()
    for node in document['nodes']:
        if not isinstance(node, dict):return None
        source = node.get('id'); reference = node.get('locator_ref')
        if (type(source) is not int or source < 0 or source in result
                or type(reference) is not str or not reference or reference in seen):
            return None
        result[source] = reference; seen.add(reference)
    return result


def public_source_identity(observation, source):
    """Copy a G2T-issued read-only reference; never infer one from an ID."""
    if observation.get('version') != DOCUMENT_VERSION:return None
    document = read_document(observation); index = _source_identity_index(document)
    if index is None or type(source) is not int or source not in index:return None
    return {'version':SOURCE_IDENTITY_VERSION,
            'namespace':{k:document[k] for k in ('session','generation')},
            'locator_ref':index[source]}


def current_source_for_identity(observation, identity):
    """Readback lookup only: never returns/rebinds an operation or authority."""
    if not isinstance(identity, dict) or identity.get('version') != SOURCE_IDENTITY_VERSION:return None
    namespace = identity.get('namespace')
    if (not isinstance(namespace, dict)
            or any(type(namespace.get(k)) is not type(observation[k]) or namespace.get(k) != observation[k]
                   for k in ('session','generation'))):return None
    index = _source_identity_index(read_document(observation))
    if index is None:return None
    return next((source for source, reference in index.items() if reference == identity.get('locator_ref')), None)


def public_object_comparison(before, after):
    """Compare public headers at exact locator refs, never infer deletion/effect.

    No old Text, value, description or operation is copied into this recurring
    comparison. Complete source material stays in its original observation.
    """
    before = read_document(before); after = read_document(after)
    result = {'version': 'jev.public-object-comparison.v1',
              'before_observation_id': before['observation_id'], 'after_observation_id': after['observation_id'],
              **{k: after[k] for k in ('session', 'generation', 'interaction_scope', 'readable_scope')},
              'identity_basis': 'G2T-issued exact BackendLocator references; not logical entity lifetime or atomicity',
              'absence_meaning': 'Not present in the later public inventory; not proof of deletion or task completion',
              'before_completeness': before['completeness'], 'after_completeness': after['completeness'],
              'task_relevance': 'not_evaluated', 'independent_task_completion': 'not_assessed',
              'is_execution_authority': False}
    if any(type(before[k]) is not type(after[k]) or before[k] != after[k] for k in ('session', 'generation')):
        return {**result, 'availability': 'unavailable_scope_or_generation_change'}
    a_ids = _source_identity_index(before); b_ids = _source_identity_index(after)
    if a_ids is None or b_ids is None:
        return {**result, 'availability': 'unavailable_source_identity'}
    for k in ('interaction_scope', 'readable_scope'):
        if (type(before[k]) is not int or type(after[k]) is not int
                or before[k] not in a_ids or after[k] not in b_ids or a_ids[before[k]] != b_ids[after[k]]):
            return {**result, 'availability': 'unavailable_scope_or_generation_change'}
    def headers(doc, ids):
        return {ids[n['id']]: {**{k: n.get(k) for k in ('role', 'label', 'states', 'partial')},
                              'parent_locator_ref': ids.get(n.get('parent'))} for n in doc['nodes']}
    a = headers(before, a_ids); b = headers(after, b_ids)
    return {**result, 'availability': 'compared_declared_public_inventories',
            'unchanged_count': sum(a.get(k) == v for k, v in b.items()),
            'changed': [{'locator_ref': k, 'before': a.get(k), 'after': b.get(k)}
                        for k in dict.fromkeys([*a, *b]) if a.get(k) != b.get(k)]}


def public_text_comparison(before, after):
    before = read_document(before); after = read_document(after)
    if 'source_identity' not in before and 'source_identity' not in after:
        return _export_key_text_comparison(before, after)
    result = {'version':'jev.public-text-comparison.v2',
              'before_observation_id':before['observation_id'],'after_observation_id':after['observation_id'],
              **{k:after[k] for k in ('session','generation','interaction_scope','readable_scope')},
              'identity_basis':'G2T-issued exact BackendLocator references in the same runtime session, application generation and public scopes; not logical entity lifetime or atomicity',
              'covers':'Complete public Text values at currently declared replace_text sources only',
              'task_relevance':'not_evaluated','independent_task_completion':'not_assessed',
              'is_execution_authority':False}
    if any(type(before[k]) is not type(after[k]) or before[k] != after[k] for k in ('session','generation')):
        return {**result,'availability':'unavailable_scope_or_generation_change'}
    old_ids = _source_identity_index(before); new_ids = _source_identity_index(after)
    if old_ids is None or new_ids is None:
        return {**result,'availability':'unavailable_source_identity'}
    for k in ('interaction_scope','readable_scope'):
        if (type(before[k]) is not int or type(after[k]) is not int
                or before[k] not in old_ids or after[k] not in new_ids
                or old_ids[before[k]] != new_ids[after[k]]):
            return {**result,'availability':'unavailable_scope_or_generation_change'}
    current = [op.get('target') for op in after['operations'] if op.get('kind')=='replace_text']
    previous = [op.get('target') for op in before['operations'] if op.get('kind')=='replace_text']
    if (any(type(source) is not int or source not in new_ids for source in current)
            or any(type(source) is not int or source not in old_ids for source in previous)):
        return {**result,'availability':'unavailable_declared_source_identity'}
    current = list(dict.fromkeys(current))
    def reads(document, index):
        values = {}
        for payload in document['text_payloads']:
            source = payload.get('source')
            if type(source) is not int or source not in index:continue
            ref = index[source]; read = payload.get('read')
            values[ref] = read if ref not in values and isinstance(read, dict) else None
        return values
    old = reads(before, old_ids); new = reads(after, new_ids); rows = []
    for source in current:
        reference = new_ids[source]; a = old.get(reference) or {}; b = new.get(reference) or {}
        comparable = (a.get('status') == b.get('status') == 'complete'
                      and type(a.get('text')) is str and type(b.get('text')) is str)
        rows.append({'source':source,'locator_ref':reference,'current_public_read_status':b.get('status','unavailable'),
                     'exported_text_equal_to_previous':a['text']==b['text'] if comparable else None})
    same = {new_ids[source] for source in current} == {old_ids[source] for source in previous}
    status = ('not_applicable_no_declared_text_targets' if not current and not previous else
              ('complete_for_declared_text_values' if same and all(r['exported_text_equal_to_previous'] is not None for r in rows) else 'partial'))
    return {**result,'availability':status,'same_declared_objects':same,'targets':rows}


def _export_key_text_comparison(before, after):
    """Literal export-key equality for history, never identity or task authority.

    Only current public replace_text targets are described. No prior plaintext,
    hash, length or removed/redacted target is exported by this comparison.
    """
    before = read_document(before); after = read_document(after)
    result = {'version':'jev.public-text-comparison.v1',
              'before_observation_id':before['observation_id'],
              'after_observation_id':after['observation_id'],
              **{key:after[key] for key in ('session','generation','interaction_scope','readable_scope')},
              'identity_basis':'Matching exported source keys only; not BackendLocator identity or execution authorization',
              'covers':'Complete public Text values at currently declared replace_text targets; no formatting or whole-task claim',
              'is_execution_authority':False,'is_task_completion':False}
    if any(type(before[key]) is not type(after[key]) or before[key] != after[key]
           for key in ('session','generation','interaction_scope','readable_scope')):
        return {**result,'availability':'unavailable_scope_or_generation_change'}
    current = [op.get('target') for op in after['operations'] if op.get('kind')=='replace_text']
    previous = [op.get('target') for op in before['operations'] if op.get('kind')=='replace_text']
    if any(type(key) is not int or key < 0 for key in current+previous):
        return {**result,'availability':'unavailable_invalid_export_keys'}
    current = list(dict.fromkeys(current)); previous = set(previous)
    def reads(document):
        values = {}
        for payload in document['text_payloads']:
            key = payload.get('source')
            if type(key) is not int:continue
            read = payload.get('read')
            values[key] = read if key not in values and isinstance(read, dict) else None
        return values
    old = reads(before); new = reads(after); rows = []
    for key in current:
        a = old.get(key) or {}; b = new.get(key) or {}
        comparable = (a.get('status') == b.get('status') == 'complete'
                      and type(a.get('text')) is str and type(b.get('text')) is str)
        rows.append({'source':key,'current_public_read_status':b.get('status','unavailable'),
                     'exported_text_equal_to_previous':a['text']==b['text'] if comparable else None})
    same = set(current) == previous
    status = ('not_applicable_no_declared_text_targets' if not current and not previous else
              ('complete_for_declared_text_values' if same and all(r['exported_text_equal_to_previous'] is not None for r in rows) else 'partial'))
    return {**result,'availability':status,'same_declared_target_keys':same,'targets':rows}
