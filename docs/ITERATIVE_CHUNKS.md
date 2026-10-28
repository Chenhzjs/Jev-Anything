# Iterative proposals: all chunks, one operation

## Current focus and selection in chunk mode

`--decision-mode iterative-current-state` is explicit, versioned as
`gui2tui.iterative-current-state.v6`. It retains the accumulated one-operation
reader and repeats `current_focus_selection` in each proposal and evaluation.
The thin wire projection copies Rust-owned public Selected/Focused flags for
all public selection-operation targets and selected/focused nodes. It does
not infer a task plan, rebuild TUI organization, filter by application/label,
rank candidates, or change source facts/capabilities. The entire original
document remains in the source store and complete scan.

`observed_state_flags` describes the same current observation;
`source_partial` preserves uncertainty, including when a flag is absent.
In contrast, a selection operation's `selected` field is the REQUESTED state
to set, never evidence of current selection. The repeated index is current
observation metadata, not a retransmission of prior chunk bodies or old
model inputs. It is rebuilt on every fresh observation and carries session,
generation, observation and scope identity with no execution authority.

The CLI's complete state index uses `jev.public-focus-selection.v4`: literal
source/parent IDs, inline role/label symbol arrays, and ordered runs of equal
state flags/partial status. Each run contains rows described by node_columns;
its flags and partial boolean apply to every row in that run. Expanding runs
and resolving inline symbols exactly reproduces the earlier object rows,
including null labels and uncertain sources. No node or value is removed.
Record framing uses at most 4096 target bytes, allowing long key inventories
to span more records; all records still reconstruct the entire original source.
The old explicit Python configuration without state_encoding retains v1
object metadata and its old requests. Encoding/framing are generic transport
policy, never application or task rules.

v4 additionally attaches `proposed_public_source` to evaluation: the exact
canonical target node and its current public Text payload/read status. The
preceding result's `public_source` carries that same-observation evidence for
the provisional target, including when a later chunk concerns another source.
This is a direct lookup in the shared Rust document, not a second organizer,
model-generated fact, inferred prerequisite, nominee or authorization. All
candidate choices and the complete original source still remain available.
This optional repeated witness uses one record frame. If a complete source
exceeds that frame, `repeat_status=source_records_only` explicitly defers the
extra copy to the complete original source records; it never truncates the
node/payload or requires a long document to fit a single request. The
preceding result retains this explicit status, not a fabricated summary.
Public-fields and member subrequests also copy the canonical operations and
public sources for every member of their legal prefix, using direct source
joins. This optional duplicate uses at most four record frames; larger whole
contexts are explicitly source_records_only, with every original still scanned.
Required schemas determine the chunk budget. A prefix attaches a whole optional
copy only if it fits the actual packet; otherwise it explicitly defers that
duplicate to source records, without reserving space for every unused branch.
Root candidate catalogs may use `jev.candidate-columns.v1` or v2: transposed inline
columns and one literal candidate-ID prefix, which reconstruct every original
row/ID exactly and preserve original order. In v2 each column is a reversible
literal, equal-value run, integer run or repeated-pattern run; encoding is
chosen only when smaller. All actual IDs and all members remain present. Member Choices still use actual
full legal IDs; no numeric-ID arithmetic or nearest-ID repair is introduced.
The old Python configuration without `public_evidence` retains its v1/v2 wire.

The v6 client can choose `jev.candidate-columns.v3` and
`jev.public-focus-selection.v6` when they reduce bytes. Reversible columns add
numeric-string runs (literal prefix/suffix, padding width and arithmetic digit
sequence), transposed run values/counts, and default values with explicit
exception positions. Candidate label references join the complete focus label
table in the **same request**, with inline extra symbols for other labels;
there are no cross-request dictionary dependencies. Global focus columns retain
every row, current flag array and partial boolean even when state runs fragment.
Exact inverse checks preserve typed values, opaque IDs and parameter suffixes.
These are transport encodings, not a second semantic organizer.

Before the first v6 model call, the client can reduce the mechanical record
frame until individual packed records fit the configured recurring request
frame. It logs the effective record size and verifies exact source reassembly.
This changes chunk boundaries, never original content, candidate membership,
order, literals or history. Fixed template byte counts are cached within one
decision, and packet size probes start near packet capacity instead of repeatedly
packing half of all remaining records. Every actual request still receives its
own byte check. An indivisible recurring frame or a growing previous model
result can still exceed the budget; that is an explicit deployment failure.
A complete scan sends all material but does not provide lossless model memory,
and more model calls may exceed the unchanged G2T observation lifetime.

After a real operation, this explicit mode also stores a mechanical
`jev.public-object-comparison.v1`: changed, newly present or no-longer-present
public headers at G2T-issued exact locator references in matching session,
generation and scopes. Header comparisons retain role, label, state, partial
and parent reference, with both observations' completeness. They never copy
old text/value/description, infer deletion or task completion, grant execution
authority or permit unknown replay. Fresh public evidence and the full goal
still determine the model's completion judgment. The complete history remains
in the source store; only the latest compatible comparison is repeated. Large
comparisons beyond four record frames explicitly use source_records_only and
a history reference; no rows are truncated or summarized away from the source.

Packing is dynamic within the configured `--chunk-request-bytes` budget:
each round accounts for its catalog, preceding result, recurring evidence and
actual encoded records. The budget is not automatic server negotiation, and
HTTP 400 is not treated as a new byte limit. Optional `JEV_DECISION_RETRIES=1`
repeats an identical **read-only model request** at most once after HTTP 400
with error code 1004. Actual identical rejected requests later succeeded in
the transport diagnostic; the server's internal cause remains unknown. The
default is zero; valid answers, 413, other errors, timeouts and GUI operations
are never retried by this policy. All HTTP attempts remain visible in provider
metadata and measured request logs; this is not best-of-two answer selection.

The ordinary G2T exact-target/ticket checks, unknown/not_attempted behavior and
readback remain unchanged. Every request is byte-checked; an oversized index
is an explicit deployment error, never an excuse to prune nodes. Existing
modes/default remain available. No improvement claim follows from this API
alone; real decisions and fresh GUI effects must be measured separately.

Additional v5 wire compression preserves the complete current state and every
prior model-result field. Large focus indexes may use
`jev.public-focus-selection.v5`, with encoded parallel columns inside each
state/partial run; smaller indexes retain v4 rows. Encodings are literal
values, equal-value `[value,count]` runs, exact `[first,step,count]` integer
runs, or `[literal_array,count]` repeated-pattern runs. These reconstruct
source references and symbol indexes exactly, not semantic ID guesses.

Public-fields Choice criteria use `[field_pairs,candidate_count]`, where each
field pair is `[index,literal]` with 0=name and 1=label; absent pairs remain
absent. This removes repeated JSON keys, retaining all public field values,
counts, legal prefix members and the original conditional decoding grammar.

Large prior-answer probability maps may use `jev.probability-columns.v1/v2`.
All keys, zero probabilities and exact numeric values remain in the same
request; nothing is dropped or rounded. Shared literal prefixes plus suffixes
reconstruct keys; v2 uses a prefix table and encoded prefix indexes. Choice,
effective assessment, canonical binding, and public-source evidence remain
plain fields. Full raw results remain in local traces, and new observations
reset the accumulated model result. This is transport compression, not a
nominee, task-completion oracle, model-result summary or execution authority.
No G2T observation TTL is extended.

## Read-only planning diagnostic (explicit experiment)

`choose_iterative(..., terminal_policy='accumulated',
planning_experiment={'preparatory_steps': False, 'repair_rounds': 0})` uses
`gui2tui.iterative-planning-experiment.v1`. This is a Python research entry,
not a Native CLI mode or a new execution path. Omitting `planning_experiment`
keeps the v8/v9 defaults and requests unchanged.

The two independent settings test generic next-step wording and at most one
post-scan repair. `preparatory_steps=True` permits a publicly supported
intermediate control/operation to advance a goal without finishing it, while
retaining exact target/parameter and goal-constraint assessment. It contains
no application, task-name or goal-specific action recipe.

`repair_rounds=1` permits one more proposal/evaluation only after the complete
source scan ends contradicted or insufficient. It sends all candidate choices
and the immediately preceding model result with empty `current_records`,
followed by the ordinary canonical chosen-operation/current-target context.
It does not retransmit old raw chunks, select a substitute automatically,
remove candidates, rescan a GUI, execute, or replay an unknown operation.
Supported/complete/wait assessments do not trigger repair. Failure or an
unsupported repaired result remains failure/abstain; there is no repeat-until-
success loop. `iterative_repair_progress` distinguishes it from source reads.

These are deployment experiments over the same public material, not a second
semantic organizer. Extra calls/packet boundaries and model memory remain
part of the measured condition. No measured benefit or default promotion is
implied; normal G2T authority and fresh observation still govern any future
execution.

The optional `diagnostic_reason` experiment key selects protocol
`gui2tui.iterative-planning-experiment.v2`, with values `off`, `log`, or `carry`.
All other settings and the old two-key v1 configuration remain valid.
`off` is the common-version control. `log` and `carry` ask the same extra
eight-option diagnostic Choice in the existing evaluation call. Categories
cover target mismatch, operation/parameter mismatch, an unmet public
precondition, goal already satisfied, a supported next step, missing public
support, unchanged irrelevant evidence, and unresolved.

The reason is a model judgment, not a fact extracted by Python. Its exact
Choice is validated, but it cannot override the assessment or select an
operation. When keep_previous/keep_complete preserves an effective assessment,
the corresponding prior model diagnosis is preserved too. In `carry`, this
diagnosis accompanies the immediately preceding result; no old raw chunk or
model-generated prose is added. In `log`, it stays in the local trace but is
explicitly omitted from the next input, including its evaluation subfield.
The two diagnostic arms use identical prompt definitions, exposing memory
transfer separately from merely asking another question. This ablation omits
only the model diagnosis, never public source material, candidates or history.
Changed packet boundaries and model beliefs remain measured limitations.

Explicit mode: `--decision-mode iterative-chunks`, protocol marker
`gui2tui.iterative-proposal.v8`. Default `full` and existing `chunk-evidence`
behavior remain unchanged. The shared document protocol is required.

```sh
PYTHONPATH=src .venv/bin/python -m jev_anything.native \
  --decision-mode iterative-chunks --chunk-request-bytes 60000 \
  --goal 'Your desktop task' --text 'literal non-secret input' \
  --output artifacts/new-iterative-run.jsonl \
  --bridge /path/to/gui2tui-agent --session desktop --app 'Chosen application'
```

For each chunk of one observation:

1. Send the goal, current raw records and the preceding model result. Ask for
   a **tentative** operation from ALL candidate IDs and exact literal bindings.
2. Make a separate evaluation call containing that proposed result and the
   same current records. Attach the full canonical operation, exact literal and
   existing reader's public target/ancestor context. Ask for one coherent
   `assessment` and a `noul` support value. Assessments are supported,
   contradicted, insufficient, complete, wait, or an explicit keep_previous.
   keep_complete is additionally available when the preceding effective judgment
   was complete, preserving that judgment when the proposal changes to done.
   supported means this exact target, operation and parameter advance the goal;
   complete means the whole GUI goal already holds. These are model judgments.
   keep_previous is offered only for an exactly unchanged proposal within the
   same observation. It preserves the preceding effective model assessment and
   binding; it does not confirm a new public fact. New contradiction/insufficiency
   revokes the binding. The binding names the candidate/operation/parameter,
   target, source hash, observation and assessment round, carries the model's
   original assessment, and is explicitly not execution authority. No prior raw
   chunk text is placed in the binding. A different proposal must be evaluated
   anew. Original user parameters stay explicit, including for done.
3. Pass only the preceding model result, including its evaluated binding, to the next chunk. Do not
   repeat the preceding chunk's raw text, accumulated evidence, raw history,
   or old requests. The same current chunk is used by its own two calls.

The evaluator must receive the proposal in its input, so these are two
sequential API calls, not two independent questions pretending to evaluate
each other's unseen answer. Jev answers structured choices/probabilities;
this mode does not assume free-form memory generation or server conversation
state. Every proposal may replace the previous one with ANY candidate.
There is no local-winner tournament, candidate pruning or restricted shortlist.

Jev's [Choice contract](https://docs.typesafe.ai/primitives/choice) permits at
most 255 options per question. At most 255 choices, including terminal choices,
use a flat Choice. Larger sets use **conditional decoding**, marked
`conditional-kind.v3`: the root chooses among the advertised public operation
kinds and done/abstain/wait; subsequent requests select only legal members of
that prefix. When the chosen kind has 2–254 distinct exact public name/label
pairs, an additional Choice copies those literal fields and the count of every
matching candidate. This partitions the entire kind without ranking targets.
Its child request repeats the same current records and all such public-field
options, without the redundant full root catalogue; every round's root still
contains every original candidate. A unique match resolves to that actual ID;
duplicates remain distinct and require subsequent exact-member selection.
With one pair or more than 254 pairs, decoding keeps the original range path.
This is a mechanical provider Choice grammar over existing canonical fields,
not another GUI organizer or a source of new labels/capabilities.
Large member sets have bounded consecutive branches, followed by
an exact candidate-ID Choice. Branch criteria give inclusive spans by first and
last actual candidate ID and count, in original same-kind catalogue order;
all rows remain in the same request. Apply the chosen kind and optional exact
public-field filter before interpreting a span; filtered member order remains
the original catalogue order. They never infer numeric ID ranges.
Member criteria use exact [field_index,literal] pairs with an explicit field
legend; absent fields stay absent. These are reversible descriptions, not new
GUI semantics. Every round starts again at the full root. A
single-member kind resolves uniquely from that explicit kind choice; it never
guesses a backend action index. Each selected operation is still evaluated
with its full definition and exact literal before any possible release.

When the preceding model has evaluated a candidate as supported in this same
observation, the root can additionally offer keep_proposal. Selecting it keeps
exactly that bound candidate, saving repeated member decoding. This is an
explicit model choice, never an automatic winner: every original kind and the
entire catalogue remain available to revise it. If the root already has 255
options, this optional shortcut is omitted. Every kept proposal still receives
a new evaluation on the current chunk; new observations reset all bindings.

The root catalogue retains every candidate in original order, with public
kind/name/label/target fields copied from the canonical operations. Repeated
scalar strings share same-request symbol arrays, checked for exact recovery;
default ID references and literal overrides are explicit. This is a wire index,
not a second TUI semantic organizer. Child choices are conditional on a logged
prefix; they do not independently nominate winners for a later tournament.
All originals remain local and all source records are scanned regardless of
the selected prefix. The old independent-digit scheme remains removed: it
produced index 1019 for 813 options in a real desktop trial. Unknown child IDs
are rejected, never repaired to a nearby candidate.

Conditional selection is not equivalent to one flat joint distribution. Kind
and branch choices can be semantically wrong, and source/order sensitivity
still needs independent evaluation. The change guarantees that valid choices
along a prefix resolve to an actual candidate, not that they select the right
one for a task.

The client retains the complete document, history and candidate bindings,
mechanically partitions them by JSON pointer and checks exact local reassembly.
Wide object key lists are also partitioned into ordered object_keys fragments,
with counts/offsets checked before any model call.

Each current packet uses `jev.record-columns.v2`: scalars remain literal,
[0,...] encodes an ordered array, and [s,...] for positive s encodes an object
under schemas[s-1]. Exact repeated values may use [-1,i] pointing to an
inline-complete shared[i] in that same packet. Shared values cannot reference
other shared values or an earlier packet. All schemas and payloads are present
in the current request. Recursive decoding must reproduce every original
record, unknown field, JSON type and order exactly. No semantic ranking or
field/region inference is performed. Consecutive outer RecordStore rN IDs can
be restored from record_ids_start; repeated outer JSON-pointer paths use
same-packet path_prefixes plus an exact suffix. Nested GUI IDs/payload fields
remain unchanged. Shared values are chosen by measured encoded-byte savings,
never semantic importance. Values shorter than 64 encoded bytes remain inline:
an aggressive 24-byte threshold retained exact source facts but confused real
target-content assessments. This is a readability tradeoff, not a guarantee of
model equivalence. The decoder also accepts v1 packets.
References reduce repeated bytes; they do
not omit facts. Packing checks the actual encoded UTF-8 body and all conditional
choice schemas. Every actual request is checked again against the configured
budget. No fixed record-count limit is introduced.

ALL records are proposed over and evaluated in original order before any
decision can be released. Early operation/done results are provisional, even
if their evaluation is positive. After the complete scan, a single final
global review receives the last model result, current proposed operation and
public target context, parameter comparisons, original user inputs and prior
executed-operation target/parameter/acceptance/effect facts. It receives no old chunk text
or independent task-oracle result. Current public facts supersede provisional
model beliefs. Its one Choice is act/done/abstain/wait, avoiding a requirement
that independent per-chunk classifiers agree about completion. act releases
only a supported actual proposed candidate; done is the final model judgment
and performs no GUI write; wait requests a new observation. When
the proposal is unchanged and a chunk is irrelevant, the prompt asks the model
to retain the preceding provisional assessment rather than forget earlier
evidence merely because its raw text is absent. A fresh observation resets
this chain. The numeric support value is recorded, with no hidden
threshold. This is the final model judgment, not an application capability
veto, backend readback or independent task-success oracle.

For each proposed operation with a string parameter, the thin reader can attach
an exact comparison against its target's complete public Text payload. This
check follows source IDs from the current shared document, returns a boolean
and length instead of carrying old chunk text, and is unavailable for incomplete
reads. It is argument equality, not task completion: other goal conditions
remain for the model to assess. The client does not map equality directly to
done or consult the independent trial oracle. This task-local argument check
does not become input to Rust's shared GUI organizer or change any capability.
Evaluations also copy the target's existing public native role, interfaces,
capabilities and text-input kind, without carrying a prior chunk's raw body.

Only this explicit mode adds client_public_text_comparison to history after a
fresh observation. For documents with `gui2tui.source_locator_refs.v1`, its v2
comparison joins G2T-issued references to exact BackendLocators in the same
runtime session, application generation and public scopes. Snapshot numeric
IDs may change. Rows contain only current public references, read status and
literal equality booleans. They contain no prior plaintext, hashes, lengths or
removed/private sources. Missing identities or scope changes are unavailable;
missing reads remain partial without hiding other known rows or operations.
References do not establish logical entity lifetime, atomicity or task relevance.
Evaluation and final-review instructions use the declared identity_basis for
available comparisons: exact-address references and legacy export-key matches
have different provenance strength. Neither is execution or task authority.
Legacy producers without the component retain v1's weaker export-key comparison;
malformed claimed components never silently fall back to strong identity.

History records the current operation's observed_source_identity. Final and
evaluation inputs may join that reference to current public target metadata
and compare complete current Text to the original parameter. Full neutral
readback rows remain visible; a changed value elsewhere does not imply goal
failure. Task relevance and independent task completion remain unassessed.
The model judges done; task_completed stays unset. The lookup never returns
an operation, ticket or permission, and never rebinds execution to a fresh ID.
The existing unknown-operation guard is retained; an additional exact-source
reference guard also blocks replay after snapshot IDs change. Dispatch still
requires the currently selected candidate, observation and operation ID.
No application/task rules, independent oracle or backing-file inspection enter
this evidence path. New source references are opaque counters, never hashes of
possibly sensitive locator strings.

The iterative CLI reuses one default requests.Session, with the existing
60-second timeout and zero automatic retries. It closes that session on exit.
JevClient also accepts a caller-owned injected session; the caller is responsible
for its transport policies and closure. Other CLI modes keep their transport.

The existing Native loop can dispatch **at most one GUI operation per complete
scan**. The next decision starts from a fresh observation and a new result
chain. Previous operation/readback history is retained and included among the
new source records. G2T still owns exact session/generation/scope/identity,
operation tickets, current capability, backend acceptance and AX readback.
`not_attempted` triggers fresh observation and a new complete scan; unknown
operations are not automatically replayed. Model done leaves independent
`task_completed` unset.

This is a **lossy finite-context decision condition**. Prior raw facts are not
simultaneously visible; a preceding proposal/evaluation can forget or distort
them. Local source retention and complete submission do not prove complete
model understanding or decision equivalence to full-context input. Complete
operation definitions are visited across chunks, and the currently proposed
definition is supplied to its evaluator; they are not all repeated in one
final body. Do not merge these results with full-context baselines. Independent
task quality, order sensitivity and omission rates require separate evidence.

If the complete candidate INDEX, preceding model result, one source record or
one evaluated operation definition cannot fit the configured encoded body
budget, stop explicitly. Nothing is silently shortened, history is not deleted,
and no candidate is dropped. Packing measures the actual encoded byte budget,
including the largest conditional choice schema and prefix receipt reserve;
there is no fixed 24-source-record packet cap. Every source record is visited.
Individual requests have one proposal/prefix question, two evaluation
questions or one final-review question, within the provider's separate
question-count limit. The
`chunk-evidence` threshold/refinement flags do not apply to this mode. Provider
failures stop the scan without dispatch, retry or server/model changes.

Trace events retain the full source, every request/response, each evaluated
round/result, errors and the one possible release. CLI traces are private and
exclusive; credentials stay outside model bodies/logs. Raw-carry/page-out
prototypes were withdrawn following user clarification; their partial results
are retained in the phase evidence and are not results of this protocol.

## Accumulated terminal experiment

`--decision-mode iterative-accumulated` explicitly selects protocol
`gui2tui.iterative-proposal.v9`. The existing iterative-chunks v8 review
baseline and default full reader remain available. Proposal/evaluation prompts,
complete records, candidates, literal bindings, current-source readback, byte
budget and authority are the same. Every record is evaluated before release.

This variant uses the last accumulated model assessment as its one terminal
judgment: complete means model done, supported can release only the assessed
actual candidate, wait requests fresh observation, and other assessments abstain.
A proposal of done alone never establishes completion. Later evidence can revoke
an earlier complete assessment. There is no second final-review classifier;
final_review is null and terminal_policy is accumulated. This avoids asking two
model judgments to agree, but can also remove a useful correction. Quality and
premature completion require separately frozen positive and negative controls.

The client never maps public parameter equality or backend acceptance to done.
The accumulated result remains a lossy model belief, not a task oracle or
execution authority. Native task_completed stays unset, G2T still validates
current operations, unknown is not replayed, and not_attempted starts a new
observation and full scan. No early complete result, candidate winner or nominee
can skip the remaining records. Experimental results must stay separate from v8.
