# Native web test results — 2026-10-17

Historical development condition. The bounded-subset nomination described below
is not the current full-context or shared-TUI default. Do not combine these
results with later prompt versions or task batches.

The generic GUI2TUI/Jev boundary completed four independently asserted browser
tasks. One public navigation remained loading and is not counted as completed.
No production code contains a site parser, configured page control labels,
DOM/CDP reads or direct GUI writes outside GUI2TUI.

| Task | Result | GUI writes | Independent evidence |
| --- | --- | ---: | --- |
| Local display preferences | Completed | 1 | Public AT-SPI checkbox is checked |
| Local catalog search for `nebula` | Completed | 2 | Server received `/results?q=nebula`; AT-SPI exposes result text |
| Local installation documentation | Completed | 1 | Server received `/destination`; AT-SPI exposes the destination text |
| Python documentation → Tutorial | Completed | 3 | Public AT-SPI document title is `The Python Tutorial — Python 3.15.0 documentation` |
| Example Domain → IANA | Not completed | 1 | Named link dispatch accepted; target remained loading through the 12-decision bound |

Jev's Python navigation took a detour through Python.org and Docs before
choosing Tutorial. This demonstrates operation discovery across different
pages with the same adapter, not optimal planning. Jev's `done` is recorded as
`model_completed`; task completion above is a separate test assertion.

The public tests exposed two relevant integration issues, addressed in this
change: a stale target rejection before dispatch now permits fresh observation
and a new decision; candidate sets larger than the request budget nominate an
action from each bounded subset before the final choice. Unknown dispatched
actions are never automatically replayed. A read-only wait permits bounded
observation while a page loads.

## Historical local evidence identifiers

- Final local tasks: `artifacts/native-web/final-local/summary.json`,
  plus JSONL decision/receipt/readback traces and `*-oracle.json` in that directory.
- Public Python task: `artifacts/native-web/python-4/summary.json` and
  `artifacts/native-web/python-4/python-oracle.json`.
- Public loading boundary: `artifacts/native-web/public-3/summary.json`
  and `artifacts/native-web/public-3/example-oracle.json`.
- Baseline commits, changed source copies, patches and hashes:
  `artifacts/native-web/source-evidence/manifest.json`.

Evidence under `artifacts/` is private local output and intentionally ignored
by Git. Earlier failed attempts remain available beside the final runs; they
are not counted as successful task results.

GUI2TUI baseline: `7bf1116119775d5038376b18d077133e3f6f8ea2` plus the local
native-bridge changes. Jev-Anything baseline:
`0cc37aab866a2876ef9b78bfd01e0b01136d851b` plus the local native client and
validation additions. These are working-tree changes, not published releases.

The final binary SHA-256 is
`377b4a1f91acf82192c77512fcb43ce1e9f8073d75827e5c38acf35b8ae4e05a`.
The tests used Firefox in Linux amd64 containers, emulated on macOS arm64.
The image identity is recorded in each summary. No API key was put in the
container or evidence; the host client read `MIYANG_API_KEY` from the environment.

Targeted validation passed: six native Python regressions, three existing
provider tests, the password-subtree export regression, four existing palette
tests and five existing runtime-authority tests. The agent binary passed local
Cargo check, Clippy with warnings denied, formatting and Linux compilation.
The full repository suites and release qualification were not run.

See [usage and limits](NATIVE_WEB.md) for commands. This is an initial native
integration test, not evidence that every website is operable. Accessibility
exposure, model choices, loading behavior, bounded context and supported input
parameters still determine which tasks can complete.
