# Jev example research and local scenario tests

Reviewed 2026-10-14 using the official documentation index:
https://docs.typesafe.ai/llms.txt

| Official example | Pattern | Local GUI scenario |
| --- | --- | --- |
| [Smart home](https://docs.typesafe.ai/demos/smart-home) | Closed-set device/action choice, unsupported requests | Living room vs bedroom light, unsupported door unlock |
| [Intent routing](https://docs.typesafe.ai/patterns/intent-routing) | Pick a handler or human review | Billing vs technical ticket assignment; insufficient information |
| [Simple memory](https://docs.typesafe.ai/cookbooks/basic_memory) | Lasting-fact gate, contextual ticket routing | Save lasting language preference vs skip today's weather request |
| [Function calling](https://docs.typesafe.ai/cookbooks/function_calling) | Closed-set function and arguments | Informs candidate-ID contract; full trading workflow deferred |
| Independent task-board fixture | Different app identity and window structure | Complete, archive or escalate a task |

The smart-home page describes a demo and says source will be released on
GitHub. We inspected the documentation, not an unpublished application.
The memory cookbook originally uses Noul for the memory gate. Our GUI adaptation
uses Choice over save/skip/review, preserving the decision intent, not claiming
to reproduce its original API or published results. We do not implement its
cross-session memory retrieval in these tests.

[Jev 1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
specifically mention literal reading, indirection, irrelevant context,
adversarial content, and option-order effects. We selected eight small cases
with paraphrased requests, negation, unsupported actions, changing visible
context and an explicit review fallback. Every case runs with both normal and
reversed option order; every request is submitted twice using the same ID to
check that retries do not repeat Jev or GUI actions.

Run `python3 scripts/scenario_acceptance.py` against the Docker workbench.
Evidence, including the real GUI2TUI scene, actual Jev answer and post-operation
scene, is saved to `artifacts/scenarios.json`.

Observed result: 22/22 passed (11 cases in both option orders), including 22
duplicate-request checks without another provider call or GUI dispatch. The
first run exposed an adapter bug: sending Escape after Enter closed the
terminal. That run correctly returned unknown effects; it was not counted as
passing. The bug was fixed and the entire scenario suite rerun successfully.

To show a scenario in the existing workbench, reset through the local API:

```bash
curl -X POST 'http://localhost:8787/api/reset?fixture=support'
```

Then use the page's goal field, for example "Assign this ticket to the
appropriate team based on its content." Available fixture names are
preferences, home, support and memory. The page's Reset button returns to
preferences. The API also accepts a `context` query parameter on reset to
replace the visible message. These fixture controls only affect the local app.

These are real local GTK interactions through GUI2TUI, with simulated domain
effects (labels in local apps). They do not control household devices, route
real customer tickets or save production memories. The task-board scenario uses
a separate application identity (`task-board`) and window title, so it verifies
cross-application configuration and adapter reuse, though it still uses GTK.
Input widgets and a second toolkit remain necessary before claiming general
application support. No formal benchmark claim is made.
