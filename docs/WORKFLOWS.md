# Record, confirm, then replay without a model

This experimental task-client layer stores a flow only after actual public GUI
operations and declared checkpoints have been recorded. It ships no website or
application flows. Human/agent task decisions create the recording; later replay
does not call a model, load provider credentials or use API tokens. There is no
automatic model fallback. Rust G2T remains the semantic organizer and authority.

The first recording interface is a semantic-command CLI/API. It is not a desktop
mouse/key recorder; automatic capture of ordinary Human TUI key use is not yet
integrated. An authorized agent can use the same API, supplying each next step
and its check. This does not automatically import or certify an old model trace.

## Recording

```sh
python -m jev_anything.workflow record \
  --name 'My task' --goal 'The actual task goal' --actor human \
  --draft /new/evidence/task-draft.json --trace /new/evidence/recording.jsonl \
  --bridge /absolute/gui2tui-agent --session desktop --app 'Observed app' --spatial-tui
```

The CLI prints the current TUI view and its public operation references. Send
one JSON command per input line. `observe` and ordinary `navigate` plans inspect
the current TUI without writing the GUI. To record one actual operation, supply
a `step`, for example using labels actually exposed by the current application:

```json
{"kind":"step","step":{"name":"open confirmation","locate":{"action":"find_action","query":"Open confirmation"},"operation":{"kind":"action","name":"click"},"after":{"kind":"control","locate":{"action":"find_action","query":"Cancel confirmation"}}}}
```

G2T finds the target. The client requires one exact matching public operation on
that current selected target, then executes through the existing bridge. A
fresh observation must establish the declared checkpoint before the step is
added. A failure stops recording. No failed step is silently omitted to promote
a successful flow. Partial evidence remains in the new trace.

Checkpoints are explicit: `control` uses another G2T find; `text` opens the shared
Reader and searches public content; `readback` requires the existing verified
primitive receipt. A text/label match or a control's presence is only that
predicate, not proof of the intended causal effect or full task success. Choose
checks that distinguish the task's intended states and review the actual result.

Finish the recording at an explicit endpoint:

```json
{"kind":"finish","endpoint":{"kind":"pause","reason":"User handoff boundary"}}
```

This creates an **unconfirmed** draft and prints its content digest. It cannot
be played directly. No password, old runtime operation IDs, locators or exact
node IDs belong in the flow's selectors. Write parameters reference explicitly
supplied literals (`--text`/`--value`) by index. Draft/evidence files are private
task data; public non-secret written values and observations are retained.

## Confirmation and replay

After a human or authorized agent reviews the exact recording and its actual
checks/results, explicitly confirm that digest:

```sh
python -m jev_anything.workflow confirm \
  --draft /new/evidence/task-draft.json --draft-digest REVIEWED_DIGEST \
  --confirmed-by human --output /new/evidence/task-confirmed.json

python -m jev_anything.workflow play \
  --workflow /new/evidence/task-confirmed.json --trace /new/evidence/replay.jsonl \
  --bridge /absolute/gui2tui-agent --session desktop --app 'Observed app' --spatial-tui
```

The recorder API is `RecordingSession.record_step`, `draft`,
`confirm_recording`; `confirmed_recipe` validates a confirmed artifact for the
runner. `confirmed_by` is explicit caller attribution, not identity
authentication. Digests detect changes after review; they are not signatures or
backend authorization. Edited flows require review/confirmation again.

Each new task invocation requires its intended starting condition. Replay always
re-observes and resolves targets anew, then G2T checks session, generation, exact
identity, current capability, scope and operation ticket. No ID from a recording
is replayed. Scope transitions are allowed only through current public facts;
application generation/owner changes stop the flow rather than rebind it.

Unknown actions are not retried. A delivered/accepted action with unknown
primitive effect can lead to a *different* recorded step only after its declared
public checkpoint is observed; its primitive receipt remains unknown. Repeating
the uncertain source/action is blocked even after current IDs change, including
across separate steps during recording. `not_attempted` gets a new observation
but stops without an automatic new attempt. Delivery errors stop further writes.

Missing/ambiguous targets, changed operations, modal exclusion, failed checks or
external human verification stop with evidence. Read-only checkpoint polling is
bounded (`--max-observations`, default 4); it never repeats a GUI write. There is
no automatic resume or durable cross-process exactly-once claim. Do not rerun a
stopped uncertain task as a retry; inspect it and explicitly establish the next
task/starting state first.

`pause` and `checkpoints_reached` are workflow outcomes. `task_completed` remains
unknown until an independent task oracle establishes it. Confirming a flow does
not make it robust to all UI versions, initial states or task variants.

## Original-GUI human handoff (workflow v2)

`jev.workflow.experimental.v2` adds an explicit human step; v1 remains accepted:

```json
{"kind":"human","name":"manual verification","instructions":"Use the same original GUI, then return","after":{"kind":"control","locate":{"action":"find_action","query":"The actual next public control"}}}
```

The runner takes a fresh observation, retires its previous operation registry,
stops automatic writes and calls a configured human handler. Without a handler
it returns `needs_human`. Cancellation returns `cancelled`. `RESUME` is only an
acknowledgement: the runner observes again and checks the explicit public
checkpoint before any further automatic step. Generation/owner changes still
stop, and unknown guards survive the pause. A manual step cannot claim a G2T
primitive readback or manufacture a receipt. It can be recorded/confirmed only
with acknowledgement and a fresh public checkpoint.

CLI `--allow-human` enables terminal acknowledgement. `--human-view-url` can
point to a user-configured original desktop; prefer `--human-view-file` for an
endpoint with a private access credential. The latter prints the private file
path without reading or recording its contents. A human handler API may instead
be attached by the calling UI. Human acknowledgement comes from the trusted
caller/input interface; it is not identity authentication.

Visual challenges require the human's access to the **same existing desktop
session**, not opening the website in a different browser. Images travel only
to the human viewer. They are not model input, AX facts or a CAPTCHA solver.
Human interaction in that external desktop is distinct from G2T's automated
operation vocabulary. AX is still authoritative for automated continuation.
If the required result is not publicly exposed, handoff can finish but automatic
continuation remains blocked/unknown rather than inventing success.

### Opt-in Docker X11 browser viewer

An existing GUI session can be shared using installed noVNC, websockify and
x11vnc. The helper does not launch a new desktop or browser, and never inspects
framebuffer data or synthesizes input. Configure the session container with
exactly one loopback publication, for example `127.0.0.1:6083:6080`, and install
the three tools there. Run the helper as the session's explicit user:

```sh
python -m jev_anything.human_view start \
  --container YOUR_GUI_CONTAINER --display :YOUR_DISPLAY --user YOUR_SESSION_UID
```

It prints paths to a fresh private state file and an `OPEN-DESKTOP.txt` access
file. The human opens that file and follows its link. A random token protects
the WebSocket route; token mapping and access files are private and outside
task evidence. Viewer logs are disabled so access tokens do not enter logs.
The internal VNC socket is loopback-only. The HTTP assets are not themselves
desktop access: missing-token connections are rejected. The helper rejects
public Docker host-port bindings. Remote machines require the operator's SSH
tunnel or separately configured authenticated TLS endpoint; this prototype is
not a public internet desktop service.

```sh
python -m jev_anything.human_view stop --state PRIVATE_VIEWER_STATE_FILE
```

Stop revokes that viewer token and terminates only its recorded process IDs
whose process start stamps still match. GUI/profile/task evidence stays intact.
The owned demonstration closes this remote input path before returning from
human acknowledgement, then G2T reacquires state. Existing external endpoints
must be closed by their configured handler/user. Fresh checks are not an atomic
transaction or exclusive lock against all human/native activity.

The viewer exposes the explicitly configured display to its authorized human,
which may be broader than one G2T modal scope; use an appropriate isolated
session. Website passwords stay in the original GUI and must not be pasted
into model messages, workflow literals or logs. This extension does not silently
detect challenge pages, auto-approve human acknowledgement or replay visual
verification actions.

### Non-Latin text in the original desktop

The browser viewer transports the original desktop pixels. Its remote GUI
environment needs fonts for the user's language. Minimal Debian/Ubuntu images
often need `fonts-noto-cjk` for Chinese/Japanese/Korean. Install it in the GUI
host/container and rebuild the fontconfig cache (`fc-cache -f`) as the session
user. `fc-list :lang=zh family` should list suitable Chinese fonts; a fallback
font without Han glyphs can show boxes even when public AX Unicode is correct.

Start new GUI sessions with an available UTF-8 locale, for example
`LANG=C.UTF-8 LC_CTYPE=C.UTF-8` after checking `locale -a`. This is display
environment setup, not a semantic/app rule. Installing fonts does not alter a
running process's locale. A public Reload may be sufficient to render with new
fonts; if the application caches its font list, a normal restart may be needed.
Confirm the actual result with the human viewer. Do not infer GUI appearance
from font metadata or use screenshot recognition as semantic evidence.
