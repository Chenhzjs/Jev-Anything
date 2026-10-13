# Jev Anything TODO

## Product definition

Jev Anything is a Jev-focused decision interface for live GUI semantics.
GUI2TUI reads and executes; Jev selects among legal candidates.

## Completed

- [x] Initialize the local Git repository and push the first plan to the
      private GitHub repository.
- [x] Add the Python Jev provider for `miyang/jev-1.13`.
- [x] Keep the API key out of source control through `.env` and `.gitignore`.
- [x] Add the initial README, product boundary and staged TODO.

## Phase 0: contract and repository

- [ ] Finish the repository package and local development instructions.
- [ ] Define versioned `Observation`, `Candidate`, `Decision` and `Outcome`.
- [ ] Define explicit states: `observing`, `candidates_ready`, `deciding`,
      `validating`, `executing`, `reading_back`, `confirmed`, `abstained`,
      `rejected`, `unknown` and `failed`.
- [ ] Define redaction rules for passwords, secrets, clipboard data and
      unrelated windows.
- [ ] Define trace IDs, timestamps, application generation and interaction
      scope.
- [ ] Keep the Jev API key in local environment configuration only.

## Phase 1: GUI2TUI observation adapter

- [ ] Connect to one reproducible Linux GUI2TUI fixture.
- [ ] Export the smallest Jev-ready observation: app, window, scene, controls,
      state, legal operations, evidence, risk, expected effect and freshness.
- [ ] Export only candidates that GUI2TUI can currently validate.
- [ ] Add static fixtures and replay so the adapter works without a live GUI.
- [ ] Verify that stale generation and changed interaction scope are visible.

## Phase 2: Jev decision adapter

- [x] Implement the `miyang/jev-1.13` decisions provider.
- [ ] Confirm the local smoke test succeeds with the current `.env` key.
- [ ] Start with `choice` for candidate selection and `noul` for abstain or
      readiness decisions.
- [ ] Return only a candidate ID or `abstain`; never accept invented actions.
- [ ] Validate unknown IDs, malformed answers, timeouts and model errors.
- [ ] Record model, request ID, latency and cost without recording secrets.
- [ ] Add a deterministic mock provider for offline development.

## Phase 3: deterministic execution loop

- [ ] Validate candidate membership, generation, scope, risk and preconditions.
- [ ] Dispatch through GUI2TUI's existing operation authority.
- [ ] Read the GUI state again after every mutating operation.
- [ ] Distinguish decision made, action delivered, effect confirmed and task
      completed.
- [ ] Never replay a stale or unknown-effect operation automatically.
- [ ] Cover success, abstain, stale, unsupported, timeout and readback-unknown.

## Phase 4: localhost workbench

The workbench is a first-class product surface and the main demo, not a
decorative dashboard.

- [ ] Create a local server with a WebSocket or Server-Sent Events event stream.
- [ ] Build a three-zone layout:
      real GUI view, semantic TUI view, and execution trace.
- [ ] Show the actual GUI state or a live capture from the Linux session on the
      left, with its app and freshness timestamp.
- [ ] Show the current GUI2TUI semantic scene on the right, including focus,
      controls, available operations and disabled states.
- [ ] Show Jev's current question, candidate set, selected answer or abstain,
      latency and request status in a compact decision strip.
- [ ] Show the running lifecycle as an event feed:
      observe, project, candidates, Jev request, decision, validation,
      dispatch, readback and outcome.
- [ ] Make every event traceable to one `trace_id` and one generation.
- [ ] Add pause, replay and reset controls for local development.
- [ ] Add explicit empty, waiting, stale, error and disconnected states.
- [ ] Keep the visual language like an engineering instrument: restrained
      typography, strong hierarchy, amber/teal status signals and no chat UI,
      oversized hero or decorative AI imagery.
- [ ] Verify the layout at desktop and narrow localhost widths.

## Phase 5: first public demo

- [ ] Use one small settings-style GUI with three visible legal candidates.
- [ ] Record a successful choice and authoritative readback.
- [ ] Record an abstain path.
- [ ] Record a stale candidate rejection after the GUI changes.
- [ ] Record an action delivery with unknown effect, without claiming success.
- [ ] Add a short README walkthrough with one command to start the workbench.

## Phase 6: benchmark foundation

- [ ] Replay the same observation and candidate set through Jev and a rule
      baseline.
- [ ] Measure candidate recall, selection accuracy, abstain quality, stale
      rejection, readback-confirmed task success, latency and cost.
- [ ] Separate model errors, candidate-generation errors and GUI execution
      errors.
- [ ] Add held-out fixtures only after the first live loop is reliable.

## Deferred

- [ ] Additional Jev tasks and `score`.
- [ ] More GUI applications and toolkits.
- [ ] MCP and SDK integrations.
- [ ] Other model providers.
- [ ] Multi-step planning and external-effect workflows.
- [ ] Public benchmark tracks and registry distribution.

## First-release acceptance test

```text
one real GUI
+ three legal candidates
+ one Jev decision
+ local validation
+ one GUI2TUI execution
+ one authoritative readback
+ one visible live trace
```
