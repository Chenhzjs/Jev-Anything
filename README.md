# Jev Anything

Jev Anything connects Jev to a live Linux GUI through GUI2TUI.

```text
observe -> candidates -> Jev decision -> validate -> execute -> readback
```

The first release is a local, inspectable workbench rather than a hidden
automation script. It shows the real application, the semantic TUI projection,
the Jev decision, and the execution evidence in one place.

## GUI2TUI submodule

This repository is the Jev integration layer. Add it to the GUI2TUI
repository as a pinned submodule:

```bash
git submodule add https://github.com/kiyotakali/Jev-Anything.git integrations/jev-anything
git submodule update --init --recursive
```

The submodule does not modify GUI2TUI. GUI2TUI remains responsible for
discovering semantic controls, enforcing scope and freshness, executing
operations and exposing authoritative readback. Jev Anything selects among
the operations GUI2TUI has already made available. See
[`docs/GUI2TUI_INTEGRATION.md`](docs/GUI2TUI_INTEGRATION.md) for the handoff
contract and the native structured-export proposal.

The package requires Python 3.10 or newer. The Docker workbench is the
recommended path when the host does not already provide a compatible Python.

## First release

The first release will support one real GUI fixture and one complete workflow:

1. GUI2TUI observes the running application.
2. Jev Anything produces a small set of legal candidates.
3. Jev chooses a candidate or abstains.
4. GUI2TUI validates and executes the decision.
5. The application is observed again and the effect is confirmed or reported
   as unknown.

The local workbench will be available at `http://localhost:<port>` and will
show:

- the current GUI view;
- the current semantic TUI view;
- candidate operations and the selected decision;
- the live lifecycle from observation through readback;
- latency, generation, scope and outcome evidence.

## Headless Docker

The supported live development environment is the Docker image under
`docker/`. It provides Linux, Xvfb, D-Bus, AT-SPI and a GTK fixture, so a
macOS host only needs Docker Desktop:

```bash
docker build -f docker/Dockerfile -t jev-anything-live .
docker run --rm jev-anything-live python3 /opt/jev-anything/live_docker_test.py
```

Start the live workbench with your local `.env` configured:

```bash
./run-demo.sh
```

Open http://localhost:8787. The left view is the Xvfb screenshot; the right
view is the actual GUI2TUI PTY. SSE delivers events during execution. Select
Jev or the rule baseline. Reset before starting a new independent scenario or
changing the fixture. A run keeps the current fixture fixed; reset first when
switching, for example `POST /api/reset?fixture=tasks`.
Pause prevents the pending decision from dispatching; it cannot undo an
operation already sent. Replay displays recorded events without executing.

Run full fixture acceptance and identical-observation model comparison:

```bash
python3 scripts/acceptance.py
python3 scripts/benchmark_replay.py
```

For package and unit-test development, install the submodule in editable
mode first: `python3 -m pip install -e .`.

These host scripts require the package dependencies (`requests` and `pexpect`).
Results are saved under `artifacts/`.
The Docker smoke test also runs the unit tests and verifies a real GUI2TUI
operation against independent, read-only AT-SPI checkbox state.

On a host requiring an HTTP proxy, set `DOCKER_BUILD_PROXY` and
`DOCKER_RUNTIME_PROXY` to an address reachable from containers, such as
`http://host.docker.internal:6152`, before the Compose command. No proxy is
hardcoded in the image. Stop with `./run-demo.sh down`.

This release is a **development fixture**, not a general GUI adapter. Its
three candidates and postconditions are fixture-specific; scene hashes are
freshness checks, not GUI2TUI generation tickets. Execution uses GUI2TUI's
advertised public operations and readback checks the actual fixture state.
Screenshots are display-only and are never submitted to Jev. No arbitrary
desktop windows are included in observations.

Jev Anything does not invent coordinates, arbitrary commands or unsupported
capabilities. The GUI2TUI operation authority remains responsible for scope,
freshness, execution and authoritative readback.

## Status

The reusable one-step plugin and its input/output contracts are documented in
[`docs/PLUGIN.md`](docs/PLUGIN.md). It handles request deduplication, stale
observations, capability gaps and unknown effects without changing GUI2TUI.
Jev-inspired local home, ticket-routing and memory-review scenarios are in
[`docs/JEV_SCENARIOS.md`](docs/JEV_SCENARIOS.md). Run them with
`python3 scripts/scenario_acceptance.py` after starting Docker.

The real Docker fixture loop and workbench have passed local acceptance. See
[`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) for measured results and gaps, and
[`docs/TODO.md`](docs/TODO.md) for the current implementation sequence.

The available stable fixture names are `preferences`, `home`, `support`,
`memory`, `tasks` and `tictactoe`. The browser fixtures `browser-home`,
`browser-support` and `browser-tictactoe` are capability probes: Epiphany is
read through AT-SPI, but the current GUI2TUI release does not expose its
WebKit page buttons as executable controls, so Jev Anything reports
`unsupported` instead of claiming success. `GET /api/config` lists each
fixture's application identity, window title and context. The plugin API is
independent of these fixtures: an adapter provides `snapshot`, `validate`,
`execute` and `verify`.

The current repository is ready for submodule-based collaboration, but the
scene-label bridge and PTY submission are still compatibility layers. Native
GUI2TUI operation IDs, generations, scopes and execution receipts remain the
next upstream integration work; this repository does not claim a general GUI
benchmark yet.
