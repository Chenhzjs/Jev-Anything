# Experimental Human TUI reader

`python -m jev_anything.tui` sends the actual Rust-rendered spatial Human TUI,
small public state records for visible targets and exact recently operated sources,
exact current operation
references, user-supplied literals and complete interaction history. It keeps the
full G2T document locally for validation. This is explicitly **partial viewport
input**, not an equivalent lossless encoding of the full document. Offscreen,
folded and other material may require navigation. The default native reader and
full-document interface are unchanged.

The Rust `tui_navigate` command performs terminal navigation/search only; it
never activates a GUI action. Query/context are literal label/title/path text,
not intent descriptions. Ambiguous search stays unresolved. `find_action`
searches the existing public-actions palette. Every actually displayed result
row has its current operation references, including nonselected rows; references
are validated against the full current G2T inventory. Python does not organize
regions, ancestry or commands.

The model returns one typed JSON plan: navigate, execute, observe, wait, done or
abstain. Execute accepts only an exact currently visible operation ID. Parameters
must reference a supplied user literal by index; navigation strings cannot become
GUI writes. There is no generated text/key/coordinate/action-index fallback.
G2T still checks current observation, identity, scope and public capability and
performs delivery/readback. Unknown effects are not replayed, even after node or
operation IDs change. Not-attempted delivery requires a fresh observation and
new decision. Model done is not independent task completion.

The explicit interface version is `gui2tui.agent.tui-text.experimental.v3`;
archived v1/v2 views remain readable for diagnostics. Reader version is
`jev.tui-reader.experimental.v3`. The current pilot transport uses the configured
DeepSeek endpoint through `DeepSeekClient.complete_json`, with no HTTP retries.
No API key belongs in a trace or command argument.

The advertised tools now include the shared Rust text Reader. `open_reader`
optionally matches a public title/query and ancestor context; multiple roots
stay ambiguous. It can address secondary documents in the same window.
`scroll_down/up` moves wrapped terminal lines within large text blocks as well
as across blocks. `open_outline` and `find_text` expose existing headings and
public text search; `choose_content` reads the selected result. `close_reader`
returns to the scene. Only currently advertised tools may be used. These tools
do not activate links, edit text or send native input.

While a Reader overlay is open, its metadata and text are retained, but covered
GUI operation bindings are absent. Python validates the public root and empty
bindings; it does not reconstruct the Rust content model or search rules.
Fresh observations refresh Reader payload and close sources that disappear or
leave the current scope. Public unavailable/partial material stays explicit.
This extension qualifies text/outline/search browsing, not new Agent table or
virtual-collection navigation.

Example (supply an existing offline tokenizer and an authorized bridge):

```sh
python -m jev_anything.tui \
  --goal 'The complete user goal' --text 'Exact user literal' \
  --counter-python /absolute/tokenizer-env/bin/python \
  --tokenizer-json /absolute/tokenizer.json \
  --max-steps 12 --max-actions 12 --max-prompt-tokens 12000 --max-input-tokens 40000 \
  --trace /new/evidence/trace.jsonl \
  --bridge /absolute/gui2tui-agent --session desktop --app 'Observed app' --spatial-tui
```

Before each provider call, the offline tokenizer counts all chat content plus a
64-token reserve. A call/prompt/cumulative budget violation stops before sending;
there is no silent cropping, history deletion or candidate tournament. Requests
and complete local observations are emitted to the newly created trace. Actual
provider usage is charged when available, otherwise the conservative estimate.
A provider deployment error is retained as an error, not repaired by dropping
semantic data. A successful small pilot does not establish stable task success,
coverage or a research-method advantage. Compare this interface separately from
complete-document and iterative-chunk conditions.

## Agent-requested human handoff

`jev.tui-reader.experimental.v2` adds the explicit plan
`{"kind":"handoff","instructions":"Use the same original GUI"}`. This is a
consumer protocol extension; the Rust TUI view remains experimental v3 and G2T
execution authority is unchanged. Existing decision evidence with reader v1
retains its original meaning.

`run_tui(..., human_handler=...)` advertises availability in the model state.
The model can request this generic handoff for credentials, security checks or
interaction that is unavailable through public capabilities. It is not an
application/page classifier or a visual solver. Without a configured handler,
the runner stops with `needs_human`; cancellation returns `human_cancelled`.

Before yielding to the human, the runner obtains a fresh observation to retire
the decision's operation registry. After an explicit resume it observes again,
checks that the owner/generation is unchanged and asks for a new model decision
using current public facts and full history. Unknown source/action guards are
not cleared. A human acknowledgement is neither a GUI primitive receipt nor
task completion. No provider calls occur while the handler is waiting, and
desktop images/credentials must not be passed back through the handler.

The CLI supports `--allow-human --human-view-file PRIVATE_ACCESS_FILE`; the file
contents are not read into model input or history. Endpoint lifecycle belongs
to the configured handler, as described in `WORKFLOWS.md`. The terminal handler
accepts only RESUME/CANCEL, suppresses POSIX TTY echo while waiting, ignores other
input without recording it, and restores terminal settings afterwards. Account,
password and verification input belongs in the original GUI, not terminal/chat.

Task evaluation may stop at an independently declared privacy boundary before
another model request, for example after reaching a private mailbox. Such an
external oracle stop must be reported separately from model done or a runner
success and must explicitly declare omitted private evidence; it is not a
lossless full-context result.


## Input representation and offline audit

Prompt `jev.tui-prompt.v7` uses explicit current-evidence checks and constrained
batches. Earlier experimental prompt versions retain their recorded meaning. The default `--input-encoding plain` keeps readable JSON. It orders
stable state fields before volatile observation identity and puts full history
last. Only object-key order changes; all fields and array order remain intact.
This may improve reusable prefixes; actual provider cache hits are not proven
by offline token counts.

Explicit `--input-encoding columns-v1` uses envelope `jev.tui-columns.v1` and
the existing checked `jev.record-columns.v2` serializer. Repeated object keys
are schemas; sufficiently long repeated values share an inline definition.
Every definition is present in the same request, all IDs remain literal, and
no prior request or provider-side expansion service is required. This is a
reversible representation of the **same partial TUI state**, including every
visible operation, parameter domain, supplied literal, unknown/future field
and full history. It does not supply the full local document to the model.
The system message includes the decoding legend.

`decode_request_state(raw, input_encoding)` audits either request form; use the
encoding recorded in its `decision_request` event. Both encodings are counted
from the final actual request before the existing budgets are checked. The
request is retained even when the budget stops delivery. No truncation,
summarization or operation nominee selection is introduced.

Columns mode is opt-in: exact decoding and lower tokenizer counts do not prove
that a model interprets it equally well. Compare small frozen tasks before
using it for a paid batch; keep its encoding and prompt version in evidence.


## Append-only requests and current-publication batches (reader v3)

The default `--prompt-mode incremental` uses `jev.tui-incremental.v2`. The first
user packet contains the initial state. Later user packets replace changed root
fields via `set`, remove named root fields via `remove`, patch immediate TUI view
fields via `view_set` / `view_remove`, and append only new `history_append` entries.
Arrays remain complete, ordered replacements. Unknown additive fields are kept;
`decode_request_state` reconstructs the entire latest state and full history.
The decoder also accepts archived incremental v1 packets.

Every earlier role/content message remains byte-for-byte unchanged. The exact
raw assistant JSON string is appended before the next user update. Historical
observations and operation IDs remain evidence only: only the latest reconstructed
view is executable. Changed or shortened existing history is rejected rather than
rewriting a cached prefix. Provider errors stop the conversation without automatic
transport retry. `--prompt-mode snapshot` remains an explicit comparison mode.

Full conversation content is still sent and counted on every call; caching is
not a promise of fewer logical input tokens or smaller HTTP bodies. Check actual
`prompt_cache_hit_tokens` and `prompt_cache_miss_tokens` usage. Stable prefixes
make reuse possible; server cache persistence and hit rates remain best effort.
No history is silently cropped to satisfy a budget. Prompt cap defaults to12k,
cumulative input to40k, calls to12; these are separately configurable. Output cap
is768 tokens to accommodate a bounded batch.

A plan may be `{"kind":"batch","operations":[{"operation_id":"EXACT_VISIBLE_ID_1",
"literal_index":0},{"operation_id":"EXACT_VISIBLE_ID_2","literal_index":1}]}`.
It contains1..4 distinct IDs, all currently visible in the same original model
observation. The complete list and literal domains are validated before dispatch.
No selector, future control, raw key or generated write text is accepted.

G2T's explicitly versioned `execute_batch_v1` consumes that observation once.
Each frozen original binding uses the existing fresh identity/scope/capability
validation and backend/readback chain. It does not translate an old locator to
an apparently similar replacement. Changed preconditions, modal exclusion,
not_attempted delivery or unknown effect stop the rest of the batch. A fresh
public observation is returned. Batches are sequential and not atomic; earlier
writes are not rolled back, and remaining steps are never silently resumed.
Task-wide unknown guards apply across single and batch plans. `--max-actions`
(default12) bounds operation attempts separately from model calls.

## Completion evidence and bounded feedback

A done plan requires1..16 current evidence predicates, for example:

```json
{"kind":"done","evidence":[{"kind":"node_state","target":106,"state":"Checked","present":true}]}
```

Supported checks are `node_state(target,state,present)`,
`node_value(target,literal_index)` or `node_value(target,value)`, and
`view_text(text)` for a nonempty literal substring. Node checks require a current public target that is visible or present in an
exact recent-operation readback. Incomplete value reads cannot establish exact value
checks; partial nodes cannot establish state checks. The client validates the
claimed fact, but relevance and coverage of every goal condition still require
model judgment. `task_completed` remains unknown without an independent oracle.

A malformed plan or unsupported done evidence records no-write validation
feedback, acquires fresh state and allows another model decision within the
original budgets. Two rejected plans stop the task; no malformed plan is repaired
into an executable operation. Repeated `observe` plans over unchanged public
state return `stalled` instead of implying success. Deliberate `wait`, local
navigation and genuinely changed observations retain their normal behavior.
Readback can establish the goal condition it directly measures; acceptance alone
cannot. Supported writes are not suppressed merely because a value already
matches, since repeated whole-text replacement may have legitimate semantics.


After an operation, `recent_operation_readbacks` joins only its G2T-issued exact
source reference with the latest public document. It copies current public fields
for that same source, even if the operation closed its palette or moved it outside
the viewport. A missing, replaced, protected or retired source is unavailable;
no name/order/ID-based rebinding is attempted. These rows never include operations
or execution authority. Invocation still requires a current visible binding.
This lets a fresh Checked state support completion while preserving the original
named-action receipt's unknown primitive effect and the no-replay guard.

`open_actions` / `open_commands` with a nonempty query use the same literal finder
as `find_action` / `find_command`, including exact/context and ambiguity behavior.
An omitted query still opens the whole local palette; a supplied query is never
silently ignored. This is explicit Human TUI search, not semantic inventory cropping.
