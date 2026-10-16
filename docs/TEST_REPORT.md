# Docker Qualification, 2026-10-14

## Plugin Follow-up

The live loop now uses the typed DecisionPlugin backend interface. Public
imports, live events and event review share its v1 records; the old simulated
engine remains legacy. Missing capability, expired observations, current
membership/scope/risk, cancellation and request deduplication have explicit
handling. See PLUGIN.md for exact guarantees and limits.

Original end-to-end suite after plugin extraction: 10/10 passed (rule and
real Jev across success, settings, abstain, stale and unknown). The expanded
scenario suite passed 22/22 with real Jev: five domain fixtures, normal and
reversed candidate order, and duplicate request submissions.

Latest Docker smoke: real GUI2TUI checkbox operation and independent AT-SPI
readback passed; 22 unit/fault tests passed. New scenario acceptance: 22/22
passed with real Jev, plus a duplicate submission for each case without
another decision or write. The domain scenarios still share a GTK harness and
simulate their domain effects locally. `tasks` uses a distinct application ID
and window title, verifying configuration reuse across application identities;
it is not a second GUI toolkit. See JEV_SCENARIOS.md for official sources,
test design and the execution defect found and corrected.

The following original measurements are retained as historical evidence.

## Environment

- macOS Apple Silicon host, Docker Desktop 29.2.1, Linux arm64 container.
- Ubuntu 24.04, Xvfb, D-Bus, AT-SPI, GTK3, Python 3.12.
- GUI2TUI commit `7bf1116119775d5038376b18d077133e3f6f8ea2`, Rust release build.
- Jev endpoint `https://miyang.cn/api/v1/decisions`, `miyang/jev-1.13`.
- Secrets excluded from Git and Docker build context; runtime environment only.

## Observed Results

| Layer | Result | Evidence |
| --- | --- | --- |
| Docker build | Passed | Native arm64 image built from pinned GUI2TUI source |
| AT-SPI | Passed | `jev-fixture`, 8 nodes, exact checkbox role |
| GUI2TUI scene | Passed | 3 bound interactive controls, no opaque/unsupported elements |
| GUI2TUI execution | Passed | Public F3 `Action: click` via actual PTY |
| Independent readback | Passed | AT-SPI CHECKED false -> true; no AT-SPI mutation |
| Unit/fault tests | 26 passed | plugin, provider, adapter and HTTP API boundary tests |
| Live acceptance | 10/10 passed in each of two runs | 5 cases each through rule baseline and real Jev |
| Identical-observation replay | 4/4 each | Both providers receive the same recorded scene/candidates |
| Browser | Passed initial QA | Real browser run button, desktop 1200px and mobile 390px screenshots |

Live cases: enable checkbox, open settings, abstain on unsupported bank
transfer, reject a stale decision after a real independent GUI2TUI mutation,
and report unknown effect for a background-refresh button with no visible
postcondition. Concurrent reset is rejected with HTTP 409. The acceptance
script checks that events are available before the final outcome.

First full live run: Jev latencies 1809, 989, 1004, 980 and 984 ms;
provider-reported total cost 0.000216804 (provider currency unspecified).
These are single-run development measurements, not statistical claims.

Raw results: `artifacts/acceptance.json`, `artifacts/benchmark.json`.
Browser images: `output/playwright/desktop.png`, `output/playwright/mobile.png`.
Generated evidence is local and ignored by Git.

## Defects Found And Addressed

- Fixed GUI2TUI companion installation paths and inspector argument forwarding.
- Added missing AT-SPI GI dependency, readiness check and exact fixture discovery.
- Fixed local API key transcription; noul and choice both returned real answers.
- Provider errors no longer masquerade as voluntary abstention in the mock loop.
- Mock close no longer claims a confirmed effect; mock provenance is explicit.
- Replaced fake GUI/TUI and post-completion animation with screenshot, PTY and SSE.
- Isolated GDK capture in a main-thread process after concurrent requests failed.
- Removed enable-toggle candidate when already checked, preventing inverse action.
- Pointed the workbench command at the Docker live service instead of the mock.

## Limits / Release Gate

This proves a real **fixture** loop. The candidate definitions and effect
assertions are specific to the fixture, not a universal GUI2TUI capability API.
The live scene hash is not GUI2TUI's native authority generation. PTY submission
is not a backend acceptance receipt. A confirmed fixture postcondition is not
a general proof that an arbitrary user's entire task succeeded; the live
outcome therefore keeps task completion unspecified.

The legacy simulated engine's contracts still differ from the public plugin.
Generic redaction, durable bounded
traces, native operation tickets, held-out benchmark tasks and broader failure
coverage remain open. Pause blocks a pending dispatch but does not cancel an
already submitted action or in-flight HTTP request. Browser QA does not yet
cover every disconnect/restart race. The initial GTK runtime emits an SVG
pixbuf-loader warning; captured checkbox state nevertheless renders visibly.

Do not label all six phases complete or publish generic benchmark scores from
these small development fixtures.
