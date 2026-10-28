# Complete shared-document reader (development)

An explicit, optional [client chunk-evidence mode](CHUNK_EVIDENCE.md) is available
for finite-context experiments. Default full mode and its single-request
contract below remain unchanged; chunk results are a separate condition.

The native loop now requests `observe_document` by default and requires
`gui2tui.agent.document.v1`. G2T's Rust implementation owns the shared TUI
organization and public source inventory. The Python reader passes the entire
document into `state.accessibility`, including additive fields, payloads,
relations, Value bounds/step, scopes and source references. It does not arrange
fields, infer regions or select a primary document.

Run with a built development G2T bridge in its Linux Accessibility session:

```sh
PYTHONPATH=src .venv/bin/python -m jev_anything.native \
  --goal 'Your desktop task' --text 'literal non-secret input' \
  --output artifacts/new-document-run.jsonl \
  --bridge /path/to/gui2tui-agent --session desktop --app 'Chosen application'
```

`--observation-format v1` before `--bridge` explicitly selects the legacy
`observe` reader. Unsupported versions/commands fail without a silent fallback.
This is a development protocol, not a published release migration guarantee.

Every operation remains in the document. Criteria include all operations with
G2T's `agent_invocable: true`; parameterized operations expand only the supplied
`--text`/`--value` literals. Missing literals do not erase the underlying public
operation or parameter domain. In document mode,
`state.candidate_representation` is `gui2tui.operation_refs.v1`: each criterion
contains an exact `operation_ref` into the complete same-request
`state.accessibility.operations`, plus its supplied `parameter` literal when
applicable. Full labels, provenance, parameter domains, target nodes, ancestors,
relations and content stay in that shared document instead of being copied into
every criterion. Internal candidates and historical receipts retain their full
execution evidence; this is protocol deduplication, not a second organizer.
Missing operation references fail before requesting a decision. Legacy v1
criteria retain their existing full descriptions. There is one decision request
with all candidates plus done/abstain/wait, without a tournament, nominee or
input size pre-rejection. This changes request expression; provider acceptance
and model comprehension require separate validation.

Full history includes prior candidates and all receipt fields, including
rejections, readback, messages and timings. `not_attempted` requires a fresh
observation and a new decision; uncertain delivery is not replayed. Observation
IDs, acquisition timestamps and timing diagnostics alone do not establish a
changed GUI consequence. Session/generation and semantic facts remain in that
comparison. G2T still consumes observations, revalidates exact identity/scope
and owns execution tickets, delivery and authoritative readback. `model_completed`
leaves `task_completed: null`.

Rust annotation v2 expresses repeated ancestor/endpoint payloads with
same-document `node_ref`, and relation reads with `relation_ref`. Their complete
canonical payloads remain in `accessibility.nodes` and `accessibility.relations`;
unknown boundary reads remain explicit. Python forwards these fields rather
than rebuilding organization. Both annotation v1 and v2 observation metadata
are excluded from consequence-change detection, so a new observation ID alone
cannot authorize replay after an uncertain operation.

Partial/unavailable AX material is retained explicitly and does not disable
other supported operations. The reader trusts G2T's public/privacy projection;
it rejects a contradictory redacted-source envelope instead of sanitizing
derived labels/relations independently in Python. It is not a second semantic
inventory validator. There is no second GUI authority or new operation kind.

The provider sends ordinary compact UTF-8 JSON (`application/json`), preserving
the decoded request object and all public text exactly. Unicode is not expanded
into ASCII escape sequences, and JSON formatting whitespace is omitted. This
needs no server extension, compression protocol or model-side decoder. Non-finite
numbers remain invalid JSON input and fail before transport; they are not clipped.

Trace events retain the full request state/questions. Timings separate bridge
round trip, G2T's exported acquisition/organization segments, literal candidate
construction, request construction, request evidence write and provider round
trip. The existing `decision.latency_ms` is the enclosing local decision time,
not model-only latency. Provider round trip includes transport/server processing;
queue/inference cannot be inferred from it. Without real inference, model and
queue timings remain unmeasured. Provider errors preserve full request evidence;
a deployment size/context limit never triggers semantic clipping.

Local validation uses deterministic loopback HTTP stubs, not model inference:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_document.py -v
```

`scripts/document_acceptance.py` additionally exercises the actual G2T JSONL
bridge and public AT-SPI on Linux, with the supplied GTK fixture and an explicit
new task plan/output directory. Its fixed test choices are confined to validation.
The P4 evidence report in the GUI2TUI workspace records the exact inputs,
binary/source hashes, full HTTP bodies and independent AX oracles. These checks
establish input/loop integration, not model decision quality, human efficiency
or independent research-task completion.
