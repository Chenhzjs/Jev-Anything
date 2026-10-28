# Generic GUI2TUI + Jev web tests

The native test path discovers operations from the live public Accessibility
scene. It requires no `ActionSpec`, webpage labels, app/toolkit adapters,
DOM/CDP or per-site backend. GUI2TUI owns operation authority. Jev only selects
an observation-local operation ID and, where needed, one supplied input value.

This development path lives alongside the original fixture workbench; it does
not change its scene-label/PTY adapter or claim general website compatibility.

## Run on a Linux browser session

Build the new source binary from the GUI2TUI checkout:

```sh
cargo build --locked --bin gui2tui-agent
```

In this repository, install the Python package and use the exported key:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
# MIYANG_API_KEY is read from the environment; JEV_API_KEY remains a fallback.
.venv/bin/python -m jev_anything.native \
  --goal 'Search the catalog for nebula and open its results' \
  --text nebula --output artifacts/catalog.jsonl \
  --bridge /path/to/GUI2TUI/target/debug/gui2tui-agent \
  --session desktop --app Firefox
```

The browser must already be displaying the target page in the same Linux
AT-SPI session. Use `--session managed` for an existing GUI2TUI managed session.
The application argument is an explicit user selection, not a production rule.
On macOS, use a Linux container and pass `docker exec -i ...` as the bridge
command. Do not pass the API key to that container: the Python client calls
Jev on the host while the bridge remains in the browser's Linux session.

`--text` is repeatable and supplies literal non-secret input candidates.
`--value` supplies numeric candidates. Jev is a decision model, so it cannot
generate arbitrary text or answers. Missing required input can yield abstention.

## Reproduce the browser checks

The acceptance runner uses the existing GUI2TUI task dependency image, three
small local pages, Firefox, Xvfb, and session D-Bus. The same native adapter
handles a checkbox, a search form, and link navigation. Page-specific strings
appear only in the validation goals and independent read-only assertions.

```sh
.venv/bin/python scripts/native_web_acceptance.py \
  --binary /path/to/GUI2TUI/target/autonomous-linux/debug/gui2tui-agent \
  --image gui2tui-task-tests:local --output artifacts/native-web/run-1
```

Add `--public-web` to include example.org and the Python documentation. Public
web pages depend on network availability and their actual Accessibility
providers; an unsupported or unknown result is evidence of a boundary.
The dependency image can be built using GUI2TUI's
`tests/research/benchmark/Dockerfile.tasks` and its documented base image.

Each run saves decision/receipt/readback JSONL, an independent AT-SPI oracle,
HTTP requests for local form/navigation effects, the binary SHA-256 and the
container image identity. Logs contain non-secret page content and supplied
input values, and should be kept private. The CLI creates its trace file with
mode 0600; the acceptance output directory has mode 0700.

## Truth and limits

- Observe/execute/quit share one persistent GUI2TUI runtime. Each observation
  contains a session, application generation, active interaction scope, nodes,
  explicit incompleteness and exact public operations. IDs are local to that
  observation, are single-use and expire after 120 seconds.
- GUI2TUI refreshes Accessibility before dispatch. It rejects changes to the
  exact target, semantic ancestry, actions, capabilities or authority. An
  unrelated control update does not invalidate a supported operation.
- Password nodes and their descendants are redacted and never offered as
  operation candidates. Native raw keys and resource export are not exposed
  by this protocol. Text replacement uses the existing bounded, authoritative
  text actuation path; complex text, selection and values require public
  backend acceptance and readback.
- A named action receipt distinguishes accepted delivery from unknown effect.
  Fresh observations can support a new decision, but an unchanged unknown
  result stops the loop. A proven rejection before dispatch permits a fresh observation and a new
  Jev decision. An unknown dispatch is never replayed. Loading pages can select
  a bounded read-only wait.
- `model_completed` is Jev's judgment. `task_completed` remains null in the
  generic runner. The acceptance runner separately asserts its known tasks
  against public Accessibility and local server observations.
- The bridge currently supports advertised actions, whole-text replacement,
  selection membership, value adjustment and numeric value setting. Range
  editing, text-selection reads, external modalities and progressive Reader
  materialization are outside this protocol's first test scope.
- The generic decision path assumes sufficient resources. It sends every
  non-redacted public node and the complete candidate set in one decision,
  retaining exact targets, ancestors, actions and literal parameters. It does
  not prune state, cap candidates or nominate from subsets.
- Actual request, context and transport constraints belong to explicit
  provider/deployment configuration. A provider rejection or timeout remains
  a provider error; it never silently removes Accessibility evidence or
  becomes a model abstention. A constrained deployment must preserve the
  semantic input or report that it cannot serve the request. For example,
  the public Miyang Decisions endpoint documents a 64 KiB request limit and
  a 32,768-token context; full-input runs can exceed that deployment's limits.
  Accessibility-unexposed controls and text cannot be manufactured by Jev.
