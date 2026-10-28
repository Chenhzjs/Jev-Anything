"""Self-contained JSON columns for one current chunk; no semantic selection."""
from __future__ import annotations

from collections import Counter
import re

from .chunked import ChunkError, _json

VERSION = 'jev.record-columns.v2'
LEGEND = (
    'current_records uses self-contained JSON columns. Scalars are literal. '
    'An array [0,...] is an original ordered array. An array [s,...] for positive '
    'integer s is an object: its keys are schemas[s-1], values are the remaining '
    'items in that order. Decode recursively. data is the complete current record '
    'list; all schemas are included in this request. [-1,i] references shared[i], '
    'an inline-complete value in this same packet, never a prior chunk; shared '
    'values contain no further shared references. No record or field is omitted. '
    'After decoding data, when record_ids_start is present, insert consecutive '
    'outer record IDs rN first in each row. An outer path [p,suffix] means '
    'path_prefixes[p]+suffix. All prefixes are in this packet; original GUI IDs '
    'and payload fields are unchanged. '
    'For example schemas=[["label","target"]], data=[0,[1,"Remove",7]] '
    'decodes to [{"label":"Remove","target":7}].'
)


def pack(records):
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ChunkError('source_integrity', 'Records must be an ordered object list')
    prefixes = []
    prefix_indexes = {}
    prefix_counts = Counter()
    for row in records:
        path = row.get('path')
        if isinstance(path, str) and '/' in path:
            prefix_counts[path.rpartition('/')[0]+'/'] += 1
    first_id = records[0].get('id') if records else None
    first = re.fullmatch(r'r(\d+)', first_id) if type(first_id) is str else None
    start = int(first.group(1)) if first else None
    sequential = start is not None and all(list(row) and list(row)[0] == 'id'
        and row['id'] == f'r{start+i}' for i, row in enumerate(records))
    normalized = []
    for original in records:
        row = dict(original)
        if sequential:row.pop('id')
        path = row.get('path')
        if isinstance(path, str) and '/' in path:
            prefix, _, suffix = path.rpartition('/');prefix += '/'
            count = prefix_counts[prefix]
            if len(prefix.encode())*(count-1) > count*8+16:
                if prefix not in prefix_indexes:
                    prefix_indexes[prefix] = len(prefixes);prefixes.append(prefix)
                row['path'] = [prefix_indexes[prefix], suffix]
        normalized.append(row)
    schemas = []
    indexes = {}
    counts = Counter()
    shared = []
    shared_indexes = {}

    def count(value):
        if isinstance(value, (dict, list, str)):
            counts[_json(value)] += 1
        if isinstance(value, dict):
            for child in value.values():count(child)
        elif isinstance(value, list):
            for child in value:count(child)
    count(normalized)

    def encode(value, references=True):
        if references and isinstance(value, (dict, list, str)):
            key = _json(value)
            if key in shared_indexes:
                return [-1, shared_indexes[key]]
            # Short literal indirection confused real target-content matching.
            if counts[key] > 1 and len(key.encode()) >= 64:
                inline = encode(value, False)
                inline_bytes = len(_json(inline).encode())
                reference_bytes = len(_json([-1, len(shared)]).encode())
                if inline_bytes*(counts[key]-1) > counts[key]*(reference_bytes+2)+16:
                    shared_indexes[key] = len(shared)
                    shared.append(inline)
                    return [-1, shared_indexes[key]]
        if isinstance(value, dict):
            keys = tuple(value)
            if any(type(key) is not str for key in keys):
                raise ChunkError('source_integrity', 'JSON object keys must be strings')
            if keys not in indexes:
                indexes[keys] = len(schemas) + 1
                schemas.append(list(keys))
            return [indexes[keys], *[encode(v, references) for v in value.values()]]
        if isinstance(value, list):
            return [0, *[encode(v, references) for v in value]]
        if value is None or type(value) in (str, bool, int, float):return value
        raise ChunkError('source_integrity', 'Unsupported non-JSON record value')

    data = encode(normalized)
    packet = {'encoding': VERSION, 'schemas': schemas, 'shared': shared,
              'path_prefixes': prefixes, 'data': data}
    if sequential:packet['record_ids_start'] = start
    return packet


def unpack(packet):
    if not isinstance(packet, dict) or packet.get('encoding') not in (VERSION,'jev.record-columns.v1'):
        raise ChunkError('source_integrity', 'Unknown current-record encoding')
    schemas = packet.get('schemas')
    if (not isinstance(schemas, list) or any(not isinstance(keys, list)
            or any(type(key) is not str for key in keys) or len(set(keys)) != len(keys)
            for keys in schemas)):
        raise ChunkError('source_integrity', 'Invalid record columns')

    shared = packet.get('shared', [])
    if not isinstance(shared, list):
        raise ChunkError('source_integrity', 'Invalid shared record values')

    def decode(value, references=True):
        if not isinstance(value, list):
            if isinstance(value, dict):
                raise ChunkError('source_integrity', 'Untagged object in record columns')
            return value
        if not value or type(value[0]) is not int:
            raise ChunkError('source_integrity', 'Invalid record tag')
        tag = value[0]
        if tag == -1:
            if (not references or len(value) != 2 or type(value[1]) is not int
                    or not 0 <= value[1] < len(shared)):
                raise ChunkError('source_integrity', 'Missing or nested shared record value')
            return decode(shared[value[1]], False)
        if tag == 0:
            return [decode(v, references) for v in value[1:]]
        if not 1 <= tag <= len(schemas) or len(schemas[tag-1]) != len(value)-1:
            raise ChunkError('source_integrity', 'Missing schema or wrong record width')
        return dict(zip(schemas[tag-1], [decode(v, references) for v in value[1:]]))

    result = decode(packet.get('data'))
    if not isinstance(result, list):
        raise ChunkError('source_integrity', 'Current records must be an ordered list')
    if packet['encoding'] == VERSION:
        prefixes = packet.get('path_prefixes', [])
        if not isinstance(prefixes, list) or any(type(p) is not str for p in prefixes):
            raise ChunkError('source_integrity', 'Invalid record path prefixes')
        for index, row in enumerate(result):
            if not isinstance(row, dict):
                raise ChunkError('source_integrity', 'Invalid record object')
            path = row.get('path')
            if isinstance(path, list):
                if (len(path) != 2 or type(path[0]) is not int
                        or not 0 <= path[0] < len(prefixes) or type(path[1]) is not str):
                    raise ChunkError('source_integrity', 'Missing or malformed path prefix')
                row['path'] = prefixes[path[0]] + path[1]
            if 'record_ids_start' in packet:
                start = packet['record_ids_start']
                if type(start) is not int or start < 0 or 'id' in row:
                    raise ChunkError('source_integrity', 'Invalid record ID sequence')
                result[index] = {'id': f'r{start+index}', **row}
    return result


def checked_pack(records):
    packet = pack(records)
    if _json(unpack(packet)) != _json(records):
        raise ChunkError('source_integrity', 'Current-record columns changed source facts')
    return packet
