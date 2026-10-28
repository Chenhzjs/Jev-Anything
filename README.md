# Jev Anything

Jev Anything connects Jev to a live Linux GUI through GUI2TUI.

```text
observe -> candidates -> Jev decision -> validate -> execute -> readback
```

The first release is a local, inspectable workbench rather than a hidden
automation script. It shows the real application, the semantic TUI projection,
the Jev decision, and the execution evidence in one place.

## Current fork and shared TUI client

This fork is maintained at [Chenhzjs/Jev-Anything](https://github.com/Chenhzjs/Jev-Anything)
from [kiyotakali/Jev-Anything](https://github.com/kiyotakali/Jev-Anything).
[GUI2TUI](https://github.com/Chenhzjs/GUI2TUI) is the primary project; this
repository is its optional `integrations/jev-anything` submodule. It can also
be installed separately. The Rust core and Human TUI do not require this client.

The current spatial-TUI client reads the actual Human renderer plus small public
state/operation references. It keeps the complete public document locally and
uses Rust navigation to reach other content. Incremental chat, bounded batches,
completion evidence and explicit human handoff are documented in
[TUI_READER.md](docs/TUI_READER.md). This is partial viewport input; it is not
a lossless full-document model prompt. It never replaces G2T execution authority.

On the Linux GUI host, install Python 3.10+ and the optional offline tokenizer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[tui]'
.venv/bin/jev-anything-tui --help
```

Configure `DEEPSEEK_API_KEY` privately in the environment and obtain a compatible
offline `tokenizer.json` for the selected model. No tokenizer weights or personal
credentials are included. Build GUI2TUI's `gui2tui-agent` from the compatible
source below, in the same Linux desktop/DBus session as the application:

```sh
.venv/bin/jev-anything-tui \
  --goal 'The complete user goal' --text 'Exact non-secret user literal' \
  --tokenizer-json /path/to/tokenizer.json \
  --max-steps 12 --max-actions 12 \
  --max-prompt-tokens 12000 --max-input-tokens 40000 \
  --trace /path/to/new-trace.jsonl \
  --bridge /path/to/gui2tui-agent --session desktop --app 'Observed app' --spatial-tui
```

The tokenizer is mandatory for pre-call budget checks; no estimated fallback or
silent context trimming is used. The trace must not already exist and may contain
public application data, so keep it private. Never supply passwords as literals.
The TUI path explicitly uses DeepSeek; `jev-anything-native` keeps Jev as its
default and supports `--provider deepseek` for full-document comparisons.

The Docker build pins GUI2TUI commit
`4c8fb7a18fce254152fca87316c8ad1325d5affa` and includes `gui2tui-agent`.
A model client can run on the host and use an authorized `docker exec -i`
bridge in the same GUI container. The old workbench below remains a separate
fixture/compatibility path; its model menu does not select the spatial-TUI loop.
See [WORKFLOWS.md](docs/WORKFLOWS.md) for recorded zero-model replay and original
desktop handoff. Viewer dependencies are explicitly configured, not auto-started.

## Generic web testing (development)

当前公共协议见 [GUI2TUI Agent protocol](https://github.com/Chenhzjs/GUI2TUI/blob/main/docs/agent-protocol.md)。
历史冻结包和原始实验材料保留在开发者本地，不属于本仓库的公开附件。

The [native web test path](docs/NATIVE_WEB.md) uses GUI2TUI's development
`gui2tui-agent` JSONL bridge. It discovers public operations without per-site
labels or scenario backends, supports `MIYANG_API_KEY`, and retains fresh
Accessibility validation and readback. The original fixture workbench below
continues to use its compatibility adapter. See the
[measured native test results](docs/NATIVE_WEB_RESULTS.md) for four completed
tasks and the recorded public-page loading boundary.

## GUI2TUI submodule

This repository is the Jev integration layer. Add it to the GUI2TUI
repository as a pinned submodule:

```bash
git submodule add https://github.com/Chenhzjs/Jev-Anything.git integrations/jev-anything
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

The scene-label bridge and PTY submission used by the old workbench remain
compatibility layers. The separate native/shared-TUI clients use GUI2TUI's native
operation IDs, generation, scope and authoritative execution receipts. They do
not claim a general GUI benchmark or universal independent task completion.
