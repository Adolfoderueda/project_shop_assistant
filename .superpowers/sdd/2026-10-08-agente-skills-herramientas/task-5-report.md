# Task 5 — Bounded local E4B native tool loop

## Implemented

- Added `OllamaShoppingAgent` with the approved default E4B model and injected `httpx.AsyncBaseTransport`; direct native `POST http://127.0.0.1:11434/api/chat`, no SDK or alternate JSON decision protocol.
- Fixed `trust_env=False`, redirects disabled, `stream=False`, `think=False`, temperature 0, context 8192 and prediction 512. One global 120-second deadline covers the conversation/cold load; connection timeout is 2 seconds.
- Sends original message text unchanged, all four fixed skills, the same seven native schemas regardless of source phrase, and complete application context at the network boundary. Identity, source update IDs and review-authority fields are excluded without editing the application snapshot. No settings, tokens, destination/address or private paths are introduced.
- Checks every serialized `{messages, tools}` UTF-8 context against 24000 bytes before any HTTP request. Overflow fails closed, without truncating proposals, rows or candidates. This is a resource bound, not a guarantee about tokenizer counts.
- Validates completion (`done is True`, `done_reason=stop`), assistant role, refusal/error status, tool-call list, native function structure and object arguments. Uses existing strict `AgentTools.validate_calls` once for the whole response before any execution. Rejects non-JSON NaN/Infinity even in otherwise unused response metadata.
- Consumes approved calls in order, at most four calls per response (existing dispatcher), four model requests and eight tools per run. A batch exceeding the remaining tool budget is not partially executed.
- Retains the full assistant message in the native transcript, then adds each read as `role=tool`, `tool_name`, JSON data; tool output never becomes system instructions. All model prose is discarded at the user-reply boundary.
- A successful mutator is terminal: returns its exact committed application reply, with no further model request or finalization. Reads accumulate existing application-rendered replies; no-tools prose becomes a controlled clarification. Later malformed output, transport failure, limits or overflow preserve earlier read results rather than replace them with invented prose.
- Cancellation propagates. Reads leave inbox pending; cancellation after a committed mutation still leaves its durable result recoverable. Storage/dispatcher execution exceptions, including SQLite failures, propagate rather than masquerading as model failures. The outer timeout handler only handles its own expired deadline.

## Interface for Task 6

```python
OllamaShoppingAgent(
    model: str = 'gemma4:e4b-it-q4_K_M',
    *, transport: httpx.AsyncBaseTransport | None = None,
)
async run(message: IncomingMessage, tools: AgentTools) -> AgentRunResult
```

- Message must equal the durable message bound to `AgentTools`; mismatch raises `ValueError` before network.
- Reasons: `terminal`, `readonly`, `clarify`, `invalid_model`, `model_failure`, `context_overflow`, `limit`.
- Counters count attempted HTTP calls and successfully returned tool executions.
- `terminal`: inbox/outbox reply already committed; do not finalize again. Reply is exactly the terminal tool reply, not a combination with preceding reads.
- Other returned results: no final inbox/outbox write here; the integration owns ordinary read/clarification completion. On cancellation without mutation, leave inbox pending for retry.
- Integration must recover existing durable results before invoking the agent, and retain its deterministic greeting/control routes. No arbitrary social-model prose is exposed by this runner.
- If reads precede a failure, `reply` is their trusted operational output and `reason` records the stopping condition. Existing reply-combiner length handling remains unchanged.

## TDD and verification evidence

All commands ran inside the assigned worktree/branch, using `C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe`, `PYTHONPATH` set to the worktree, and shell timeout 600000 ms.

1. **Initial RED:** `python -m pytest tests/test_agent_ollama.py -q` — **36 failed in 3.96s**. Tests collected successfully, then failed with expected absent `shopping_agent.ollama` import.
2. **Initial GREEN:** same command — **36 passed in 2.32s**.
3. Added further read-failure, full tool-context overflow, reviewed-permission exclusion and post-commit cancellation coverage — **41 passed in 7.01s**; focused Ruff check passed.
4. **Self-review RED:** added non-JSON numeric constant regression — same focused command: **1 failed, 41 passed in 2.86s**. A NaN metadata response incorrectly reached a valid cancellation tool (`terminal` rather than `invalid_model`). Added strict finite-JSON validation before batch approval/execution.
5. **Final focused GREEN:** same command — **42 passed in 2.88s**. `python -m ruff check shopping_agent/ollama.py tests/test_agent_ollama.py` — **All checks passed!** `git diff --check` clean.
6. **Full suite, once before commit:** `python -m pytest -q` — **1134 passed in 291.99s (0:04:51)**, exit code 0, no warnings/failures.

All network fixtures use `httpx.MockTransport`, with real temporary repositories/tools and native HTTP response fixtures. Coverage includes original payload/settings/schema independence, transcript shape, read-then-prepare, terminal false-prose suppression, malformed/unknown/refusal/truncated response rejection, redirects/network errors, full-batch validation, both budgets, controlled no-tools replies, overall timeout, cancellation and durable post-commit recovery, overflow without HTTP, overflow following real read data, privacy/permission exclusion, and SQLite exception propagation.

## Files changed

- `shopping_agent/ollama.py` (new)
- `tests/test_agent_ollama.py` (new)
- `.superpowers/sdd/2026-10-08-agente-skills-herramientas/task-5-report.md` (new)

## Self-review / concerns

Read the complete production implementation and reviewed the test coverage against the task brief, binding spec, plan constraints and Task 4 interface. Fixed the permissive numeric decoding issue via RED/GREEN before the final full-suite run. Reused contracts/tools/replies/skills unchanged; no unrelated redesign or dependencies.

No blocking concerns. Native request/response/tool transcript shape was checked against Context7 `/ollama/ollama` API documentation. Actual E4B interpretation/latency validation is deferred to Task 7; the byte cap intentionally does not promise 8192-token fit. Wheel verification remains deferred by controller instruction. No real model, installs, settings/private data, bot/Telegram, merge or push were used.
