# Plugin contract

The public Python imports from `jev_anything` are ActionSpec,
Gui2TuiSceneAdapter, Candidate, Observation, Decision, Outcome, RunResult,
DecisionPlugin and JevClient. Their serialized
forms have explicit v1 versions. `models.py` belongs to the old simulated demo
and is not the live/plugin contract.

```python
from dataclasses import asdict
from jev_anything import DecisionPlugin, JevClient

plugin = DecisionPlugin(backend, max_age=30)
result = plugin.run(
    "Route the current ticket to the appropriate team",
    JevClient(),
    request_id="ticket-42-attempt-1",
)
print(asdict(result))
```

`backend` is an adapter implementing `snapshot`, `validate`, `execute`, and
`verify`. No upstream GUI2TUI changes are required. LiveSession is the current
Docker adapter; it implements that interface using the existing inspector and
public terminal operations. Candidate and expected-effect definitions come
from explicit scenario configuration, not model-generated commands.

For a GUI2TUI scene adapter, configure `ActionSpec` values and call
`Gui2TuiSceneAdapter.observe(scene)`. It verifies the exact scene title, hashes
the complete scene as the freshness generation, and emits only configured
controls with a GUI2TUI binding. If the scene has no configured executable
actions it raises `CapabilityUnavailable`; this is how browser pages and
read-only windows are reported instead of silently becoming model abstentions.

Input: user goal plus an Observation containing current scene, freshness,
interaction scope and Candidate objects. Output: RunResult containing a
Decision (candidate ID or null for abstain) and an Outcome. Failures before
decision can have a null Decision. All lifecycle events share a trace ID and
request ID; live execution and stored event review use the same records.

Sequence: snapshot -> validate advertised candidates -> Jev choice ->
validate operation -> re-snapshot and compare -> execute -> snapshot -> verify.
The adapter raises CapabilityUnavailable for missing/ambiguous bindings or
unavailable operations; the plugin reports `unsupported` before dispatch.

Outcomes: confirmed, abstained, rejected, unsupported, failed, unknown. Every
outcome also carries a stable `error_code` when a reason exists, including
`capability_unavailable`, `model_abstained`, `unknown_candidate`,
`stale_or_disallowed`, `provider_or_validation_error` and
`execution_unknown`.
Provider timeout is failed with no dispatch. Expired observations, changed
scope/state, unknown IDs and disallowed candidates are rejected. Exceptions
after entering execution are conservatively unknown. There is no automatic
retry. `submitted_to_gui2tui` describes terminal submission, not an upstream
acceptance receipt. `task_completed` stays null: a postcondition is not proof
of a general task's completion.

Reuse the same request ID when retrying transport: in the same plugin instance
it returns the original RunResult without repeating Jev or GUI writes. A
different goal/model/options with that ID raises ValueError. IDs are retained
in memory only, including across fixture resets, not process restarts. A new
request ID represents a new user-authorized attempt. There is no cross-process
exactly-once guarantee; never automatically retry unknown effects after restart.

JEV_TIMEOUT_SECONDS controls the provider timeout (default 60). Observation
max_age defaults to 30 seconds, so a slow valid response can still be rejected
as expired. Cancellation prevents pending dispatch; it cannot undo a submitted
operation. Scene hashes are a best-effort freshness check, not native GUI2TUI
tickets. A race remains between the final observation and terminal submission.

The adapter configuration supplies application identity, window title and
candidate definitions; the plugin itself does not contain an app name. The
current risk allowlist permits local fixtures only. Arbitrary app support,
native receipts, redaction and durable traces remain separate work. Adding a
scenario requires descriptive labels, bindings visible in GUI2TUI, and a
readback predicate; do not invent capabilities the backend does not expose.
