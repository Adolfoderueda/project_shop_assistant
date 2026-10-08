# Task 6 implementation report

## Implemented

- Added opt-in `AgentConversation`, recovering durable replies and committed presentation jobs before route/context reads; slash commands and explicit purchases remain deterministic.
- Reused the existing whole-message greeting predicate (extracted without adding vocabulary). Greetings read no private list rows; native and slash queries preserve pending proposals and TTL.
- Natural aliases never enter the legacy parser. Verified slash-origin answers call repository dialogue transitions directly; agent controls use the durable repository. Model prose is discarded and native-tool replies remain application-rendered.
- Recorded command provenance inside `_apply_dialogue`'s caller transaction. Consumption, replacement and incompatible proposals clear links; committed duplicate-choice/add-quantity continuations retain their verified provenance. New agent proposals clear incompatible legacy state.
- Added validated engine/model settings, opt-in runtime construction without an extra reply writer, and optional legacy route synchronization after durable recovery. First legacy synchronization preserves existing legacy memory.
- Added `agent-local enable|disable|status`, lock-protected explicit permission revocation before saving settings, E4B availability checks, and valid `model-local disable` rollback to commands-only/legacy. Failed saves do not restore permissions. Status is read-only and can run while the worker is locked.
- Doctor displays engine/model without generating or downloading text; README documents separate installation/activation and permission-safe rollback.

## TDD evidence

All commands used the existing interpreter:
`C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe`.
PowerShell set `$env:PYTHONPATH=(Get-Location).Path` to this worktree. Commands had timeout 600000 ms.

### RED

`python -m pytest tests/test_agent_conversation.py tests/test_agent_runtime.py -q`

Result: **4 failed, 7 errors in 9.10s**. Expected missing integration module, missing settings fields and CLI function; the model-local rollback assertion also failed because engine rollback/revocation was absent.

Additional focused RED cycles:
- `tests/test_agent_conversation.py`: incompatible legacy pending state retained `command_update_id=1` (failure before clearing replaced focus).
- `test_route_discard_emits_controlled_notice`: missing controlled notice.
- `test_first_legacy_route_does_not_discard_existing_legacy_memory`: real pending state became `None` after first synchronization (after correcting the test interpreter to create actual pending memory).
- `test_slash_query_preserves_proposal_and_command_continuation`: `/lista` incorrectly cleared the agent proposal.

The duplicate continuation test initially used an unsupported short answer; corrected it to the existing genuine answer `añadir otra línea`, without extending parser vocabulary.

### GREEN

`python -m pytest tests/test_agent_conversation.py tests/test_agent_runtime.py tests/test_agent_storage.py tests/test_runtime.py tests/test_ollama_interpreter.py -q`

Result before full run: **153 passed in 62.98s**.

### Full suite (run once as requested)

`python -m pytest -q`

Result: **2 failed, 1154 passed in 305.08s**.
Failures:
- `tests/test_agent_recovery.py::test_v8_migration_preserves_all_old_tables`
- `tests/test_presentation_storage.py::test_v6_upgrade_preserves_all_durable_work`

Root cause: upgrade fixtures legitimately prepare legacy dialogue work using pre-agent schemas; the new provenance bookkeeping unconditionally accessed `conversation_routes`. Fixed by checking schema availability before the added bookkeeping, preserving pre-agent legacy behavior without changing migrations or tests.

### Final focused verification, including both full-suite failures

`python -m pytest tests/test_agent_conversation.py tests/test_agent_runtime.py tests/test_agent_storage.py tests/test_agent_recovery.py tests/test_presentation_storage.py tests/test_runtime.py tests/test_ollama_interpreter.py -q`

Result: **183 passed in 68.79s**, no warnings. The two failed full-suite tests now pass. No second full-suite run, respecting the requested full-once workflow.

`git diff --check`: no whitespace errors (Git emits local LF/CRLF conversion notices).

## Files changed

- `shopping_agent/conversation.py` (new)
- `shopping_agent/storage.py`
- `conversation.py`
- `dialogue_storage.py`
- `dialogue_requests.py` (extract authoritative whole-message greeting predicate)
- `config.py`
- `runtime.py`
- `cli.py`
- `README.md`
- `tests/test_agent_conversation.py` (new)
- `tests/test_agent_runtime.py` (new)
- This report.

## Self-review and assumptions / concerns

- Self-review caught first-legacy-route memory loss and slash-query proposal consumption; both received focused RED/GREEN regression tests.
- Controlled incompatible-memory discard notices are written to the allowlisted local worker log, not appended to Telegram replies. README makes this explicit. This preserves existing deterministic/committed reply content, but the controller should confirm that a local notice satisfies the intended aviso requirement.
- Final full-suite result is not claimed green: the single full run had the two migration regressions above, subsequently fixed and verified in the 183-test focused run.
- Existing large dialogue/repository files were changed narrowly; no parser redesign or unrelated refactoring.
- No dependencies, private original settings/list, real model calls, Telegram, restarts, model activation, merges or pushes. HTTP model verification uses MockTransport; runtime/CLI tests use temporary repositories/settings and injected offline collaborators. Wheel deferral remains unchanged.

## Pre-review concern resolution: durable user-visible discard notice

The controller clarified that the local log alone does not satisfy spec §7. This
supersedes the notice concern and the incomplete full-suite baseline above.

### Changes

- `set_conversation_route` now queues a separate, application-owned UUID outbox
  notice (`update_id=NULL`) in the same write transaction that discards incompatible
  context and updates the route. Its fixed Spanish text tells the user to reformulate
  and review a new proposal, and states that saved entries have not changed.
- The recipient comes only from the validated route identity (strict positive
  integer user ID and matching private chat ID), never proposal JSON. Existing
  owner assertions continue to validate the resulting outbox.
- Same-route replay does not enqueue another notice. A genuine preserved slash
  continuation produces none. Failed outbox insertion rolls back invalidation and
  route mutation together. Neither primary inbox replies nor proposal review
  outbox witnesses are rewritten.
- README now documents the independent durable Telegram notice; the controlled
  local log remains supplementary.

### RED / GREEN evidence

Same interpreter/PYTHONPATH as above; all commands used timeout 600000 ms.

RED: `python -m pytest tests/test_agent_route_notices.py -q`

**8 failed, 1 passed in 1.11s**: no standalone notice existed, injected notice
failure did not abort the transaction, and invalid private route identities were
accepted. The preserved-continuation fixture initially started on the already
selected agent route; corrected it to begin the slash command on legacy before
testing the route transition, without changing production continuation behavior.

GREEN focused:
`python -m pytest tests/test_agent_route_notices.py tests/test_agent_conversation.py tests/test_agent_runtime.py tests/test_agent_storage.py tests/test_agent_recovery.py tests/test_presentation_storage.py -q`

**117 passed in 38.47s**, including actual outbox contents, saved-row and committed
review preservation, restart/replay deduplication after delivery, transactional
rollback, preserved genuine continuation, invalid identities, and corrupted
proposal payload recipient isolation.

FINAL full integration baseline: `python -m pytest -q`

**1165 passed in 316.34s (0:05:16)**, no warnings or failures. This also verifies
the two migration fixes from the earlier full run.

Self-review: read the notice transaction/identity validation diff and new tests;
`git diff --check` has no whitespace errors (only local LF/CRLF conversion notices).
No outstanding task-6 concerns from this correction. No external activation,
real Telegram/model calls, dependencies, subagents, merge or push.

Files in this correction: `shopping_agent/storage.py`, `README.md`, new
`tests/test_agent_route_notices.py`, and this report.
