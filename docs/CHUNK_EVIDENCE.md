# Experimental client evidence chunks

For a complete iterative scan carrying only the preceding tentative operation
and its model evaluation, see [Iterative chunks](ITERATIVE_CHUNKS.md). That
separate opt-in mode never carries previous chunk text or executes per chunk.

`--decision-mode chunk-evidence` explicitly enables
`gui2tui.chunk-evidence.v1`. Default `full` mode is unchanged. There is no
automatic 413 fallback, server upload/session requirement, or new GUI authority.

```sh
PYTHONPATH=src .venv/bin/python -m jev_anything.native \
  --decision-mode chunk-evidence --chunk-request-bytes 60000 \
  --goal 'Your desktop task' --text 'literal non-secret input' \
  --output artifacts/new-chunk-run.jsonl \
  --bridge /path/to/gui2tui-agent --session desktop --app 'Chosen application'
```

The client retains the complete shared document and history. Mechanical JSON
pointer records preserve every field/type, array order and complete text,
including Unicode tails. Large strings use explicit code-point offsets, total
length and start/end flags for the original string; local
reassembly is checked before any model call. All records are submitted across
reader requests, each within the explicit byte budget and 24-question limit.
Rust still supplies every GUI field, region, relationship and annotation.

Readers answer only per-record `noul` relevance probabilities. They cannot choose
an action, eliminate a candidate, or establish done. The final request includes
ALL candidate IDs/literals and complete canonical operation definitions, with
exact duplicate provenance objects shared in a same-request catalogue. The
definition map key supplies the original operation ID. Full history and the
original source/scope/completeness metadata remain available to that final call.

The final model receives selected verbatim records. It can request inspection
of a local JSON neighbour or an explicit canonical source reference. If it asks
to inspect, its simultaneous action/done answer is ignored. Inspection can
continue up to `--chunk-max-refinements` (default 4); exhaustion stops without
GUI dispatch. String fragments retain their canonical public text-source links.
Unknown/unavailable source material stays unknown; local inspection does not
create missing backend payloads or capabilities.

**This is a lossy finite-context decision condition.** Complete local storage
and complete reader coverage do not mean the final model simultaneously sees
all original facts. `coverage.selection_lossy` and
`coverage.full_material_in_final_request` report that distinction. Relevance
probabilities are not evidence truth or independent task-completion oracles.
Do not merge results with single-request full-context experiments.

If all candidate definitions/history, selected evidence, inspection choices or
one reader packet cannot fit, the mode reports an explicit budget failure. It
does not discard candidates, rank local winners, evict selected evidence, clip
history or silently shorten content. Some large candidate universes therefore
remain unsupported. The byte guard belongs to this explicit transport mode;
the default full mode has no restored 64-KiB local pre-rejection. Provider token
limits, rate limits and failures can still stop a run; there is no automatic
retry or switch of model/deployment. Reader calls are sequential and their
count/cost can be much greater than one GUI step.

`--chunk-request-bytes` measures the entire encoded JSON body, including model,
state and questions. It can be adjusted within the deployment's actual limit;
the client does not increase the provider's limit. Raising it may let one final
request fit but does not solve every candidate/history or evidence overflow.

Trace events retain full source material (`chunk_source`), the plan, every
request/response and usage, relevance scores, exact inspected records, ignored
intermediate actions and failures. CLI output files are exclusive/private.
Credentials remain outside body/logs. No evidence is reused across observations.

After the final answer, the existing Native loop and G2T execute path remain in
charge. G2T consumes observations and revalidates session, generation, scope,
exact identity/capability, ticket, acceptance and authoritative readback.
`not_attempted` starts a fresh observation and full new chunk decision;
unknown operations are not replayed. Final model done still leaves independent
`task_completed` unset.
