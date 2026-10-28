# DeepSeek full-context provider

Use the existing document reader and authority loop with the explicit option
`--provider deepseek --decision-mode full`. Configure `DEEPSEEK_API_KEY` only in
the environment. Jev remains the CLI default; setting a DeepSeek key does not
silently change another experiment's provider.

The thin adapter sends every state field, original document node/payload/relation,
legal candidate and history item in one JSON chat request. It does not organize
GUI semantics, prune candidates, split source content, retry failed requests,
repair IDs or execute anything. JSON output is accepted only when every answer
has the requested type and every choice is an exact legal key. An empty,
truncated, malformed or out-of-set response fails explicitly. The G2T current
observation, identity, capability, acceptance and readback checks are unchanged.

Defaults: official `deepseek-flash`, thinking disabled, 512 maximum output tokens,
60-second HTTP timeout, zero retries. Override the model/endpoint/timeout using
`DEEPSEEK_MODEL`, `DEEPSEEK_API_URL`, `DEEPSEEK_TIMEOUT_SECONDS` when explicitly
needed. An HTTP connection is reused throughout the CLI run. The output budget
does not crop the input. A provider context/body rejection stays a deployment
failure; no fallback or input removal is performed.

The official context is 1M tokens, not unlimited. A measured complete Writer
observation with 1,987 public nodes and 3,422 candidates used 900,895 prompt tokens
and 19 completion tokens in one request (16.73 seconds). This establishes input
feasibility and a legal returned ID, not correctness or task completion.

## Lossless full-state encoding

`DEEPSEEK_INPUT_LAYOUT=lossless-state-v1` explicitly enables experimental input
compression. The existing reversible `jev.record-columns.v2` codec encodes the
complete state with shared object schemas and inline repeated values. The
questions and every legal criterion remain normal JSON. The system message
documents the encoding, and `decode_deepseek_input` reconstructs the complete
original state and questions exactly. This is a wire representation, not a
second semantic organizer. It preserves array order, literal IDs, types, unknown
fields, full bodies, relations, fresh authority metadata and all history.

On the same large Writer input, the measured prompt fell from 900,906 to 508,095
tokens (43.6%), with 19 output tokens and 8.51 seconds total client wall time.
The returned choice was legal; no GUI operation was performed by this transport
measurement. Encoding both state and questions together instead returned an
empty answer in the first trial; that variant was not adopted. A different
document-only encoding saved only 17 further tokens and was not adopted either.
The retained transport must not be interpreted as proving equal model decision
quality: small real-source checks varied across trials even with plain JSON.
In a separate frozen diagnostic on four desktop goals repeated twice, plain
JSON hit the provisional known-admissible next-step set in 5/8 decisions and
compressed input in 3/8, with all 16 choices legal. This small diagnostic does
not establish a universal difference, but it does not justify replacing the
plain default. No model choices were executed in that diagnostic.

`DEEPSEEK_INPUT_LAYOUT=cache-prefix-v1` remains the default plain JSON format
with object keys reordered. `canonical` retains the original object key order.
All three layouts decode to the same input values. Neither override crops or
splits input, repairs model output, or changes G2T execution authority.

## Cache accounting

DeepSeek's prefix cache is enabled by the service. The client does not substitute
old observations or retain old authority. It still sends the entire current
request. Cache hits are best effort, depend on exact reusable prefixes and
persistence, and do not reduce context-window occupancy. Record the actual
`usage.prompt_cache_hit_tokens` and `prompt_cache_miss_tokens`; do not assume a
hit from repeated-looking text.

A three-request read-only replay of three real complete observations measured
0, 269,824 and 258,304 hit tokens. The last two were approximately 30% and 29% of
901,822 and 902,476 prompt tokens; request times were 11.34 and 13.27 seconds.
These are transport/cache diagnostics, not live GUI task success or a controlled
model-quality comparison. The first real Writer task attempt with canonical
ordering used 2,711,454 input plus 70 output tokens in four calls and ended
unknown after a public Selection rejection; its independent oracle was false.

Evidence identifiers: `deepseek-full-20261027-114842` and the separate
lossless-input/repeated-validation batch `token-and-validation-20261027-131711`.
Their raw artifacts remain private local development evidence and are not
included in this repository.
Do not pool their task success rates: source revisions, transport conditions and
initial public startup dialogs differ. Cache statistics for the old plain JSON
format do not establish the cache behavior of the new encoding.

Primary API documentation:
- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/json_mode/
- https://api-docs.deepseek.com/guides/kv_cache/
