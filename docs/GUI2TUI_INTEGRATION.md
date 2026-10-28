# GUI2TUI integration

Jev Anything is an integration layer that can be mounted into the GUI2TUI
repository as a Git submodule. It asks Jev to choose between operations that
GUI2TUI has already exposed and validated. It does not replace GUI2TUI's
inspection, focus, scope, execution or readback authority.

## Add this repository as a submodule

From the GUI2TUI repository:

```bash
git submodule add https://github.com/Chenhzjs/Jev-Anything.git integrations/jev-anything
git submodule update --init --recursive
```

Pin the submodule to a reviewed commit in the GUI2TUI repository. A checkout
of GUI2TUI should then be reproducible with:

```bash
git clone --recurse-submodules <gui2tui-repository>
```

The submodule is independently installable when its Python API is needed:

```bash
python3 -m pip install -e integrations/jev-anything
```

For the shared spatial-TUI runner, install `integrations/jev-anything[tui]`
instead. The installed command is `jev-anything-tui`; it consumes the Rust
renderer through `gui2tui-agent --spatial-tui`. See [TUI_READER.md](TUI_READER.md)
for budgets, the required offline tokenizer, exact-publication batches and
incremental messages. Model configuration stays in the environment.

GUI2TUI is the primary repository. Jev is optional: ordinary Rust builds and
Human TUI usage must work without initializing the submodule. The two projects
communicate through the versioned JSONL bridge; neither imports the other's
source tree. Keep the existing standalone developer checkout in place. The
submodule is a separate checkout pinned to an explicit reviewed commit.

The Docker build in this fork pins GUI2TUI
`4c8fb7a18fce254152fca87316c8ad1325d5affa`, including `gui2tui-agent`.
Updating the parent submodule pointer does not implicitly change that build pin.
Review both when upgrading protocol versions. There is no recursive submodule
back from Jev to GUI2TUI.

The Docker workbench remains the reference live environment because it
provides Linux, Xvfb, D-Bus, AT-SPI and the GUI2TUI fixture:

```bash
cd integrations/jev-anything
cp .env.example .env
# Put the local JEV_API_KEY in .env.
./run-demo.sh
```

## Responsibility boundary

GUI2TUI owns:

- discovering the active application and semantic scene;
- assigning stable operation IDs and reporting available operations;
- enforcing application, window, focus and interaction scope;
- rejecting stale operations before dispatch;
- executing an operation and returning an execution receipt;
- providing authoritative post-operation state.

Jev Anything owns:

- converting a GUI2TUI scene into `Observation` and `Candidate` records;
- asking Jev to select one legal candidate or abstain;
- validating the decision against a fresh observation;
- calling the GUI2TUI operation interface;
- reading back state and returning `Outcome`.

The stable plugin chain is:

```text
read -> candidates -> Jev decision -> validate -> GUI2TUI execute -> readback
```

The plugin never accepts a model-generated command, coordinate or arbitrary
operation. If GUI2TUI does not expose a required semantic operation, the
result is `unsupported` with `capability_unavailable`.

## Historical workbench bridge and migration proposal

This section describes the older fixture/PTY adapter. Native and shared-TUI
clients now exist independently in `native.py` and `tui.py`; the old workbench
does not automatically route through them. The proposal below is retained as
historical context, not a claim that the new native authority is absent.

The current `Gui2TuiSceneAdapter` consumes the text produced by
`GUI2TUI --dump-scene`. It uses configured labels and visible bindings to
construct candidates, hashes the scene as a temporary freshness generation,
and dispatches through the existing public PTY operation. This is sufficient
for the current Docker fixtures and deliberately keeps the upstream GUI2TUI
code unchanged.

The adapter should move to a native structured export when GUI2TUI provides
one. The proposed boundary is:

```json
{
  "application": "example",
  "window": "Example Window",
  "generation": "native-generation",
  "interaction_scope": "native-scope",
  "elements": [
    {
      "id": "save-button",
      "role": "button",
      "label": "Save",
      "enabled": true,
      "operations": [
        {
          "id": "save",
          "intent": "click",
          "risk": "local_fixture_only"
        }
      ]
    }
  ]
}
```

Dispatch should accept the operation ID plus the observed generation and
scope, then return a receipt such as:

```json
{
  "accepted": true,
  "operation_id": "save",
  "generation_before": "native-generation",
  "generation_after": "next-generation",
  "status": "submitted"
}
```

Until this exists, scene hashes and PTY submission must be treated as
best-effort evidence. They are not native GUI2TUI tickets or acceptance
receipts.

## Python entry point

The v1 public imports are exported from `jev_anything`:

```python
from jev_anything import DecisionPlugin, JevClient

plugin = DecisionPlugin(gui2tui_backend)
result = plugin.run(
    "Route the current ticket to support",
    JevClient(),
    request_id="ticket-42-attempt-1",
)
```

The backend implements four operations:

```python
class Backend(Protocol):
    def snapshot(self) -> Observation: ...
    def validate(self, candidate: Candidate) -> None: ...
    def execute(self, candidate: Candidate) -> None: ...
    def verify(self, candidate, before, after) -> bool | None: ...
```

`RunResult` contains the selected candidate (or abstention), trace and request
IDs, and an `Outcome`. The outcome distinguishes `confirmed`, `abstained`,
`rejected`, `unsupported`, `failed` and `unknown`. Unknown means that an
operation may have been submitted but its effect was not established; callers
must not retry it automatically.

## Verification for a GUI2TUI change

Run the package tests first:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

Then run the live Docker checks from this repository:

```bash
python3 scripts/acceptance.py
python3 scripts/scenario_acceptance.py
```

The current checks cover real AT-SPI discovery, GUI2TUI scene inspection,
public terminal execution, independent readback, Jev and rule decisions,
stale and unknown outcomes, cross-application configuration reuse, browser
capability gaps and the Tic-Tac-Toe loop. They are development acceptance
tests, not a general benchmark.

## Upstream collaboration checklist

- [ ] Replace label matching with native structured scene export.
- [ ] Expose stable operation IDs, generation and interaction scope.
- [ ] Expose precondition validation and execution receipts.
- [ ] Expose authoritative post-operation readback.
- [ ] Define redaction for secrets, clipboard data and unrelated windows.
- [ ] Keep the Jev plugin as a separate integration package and pin it from
      GUI2TUI instead of copying its source into the GUI2TUI core.
