# Final-review fix report — DONE_WITH_CONCERNS

## Scope and root cause

Worked only in the isolated `skills-agent` worktree, `feat/skills-agent`, starting
at `1a4123f`. No subagents, unrelated behavior changes, prompt/model/schema/oracle
tweaks, private data/Settings, Telegram, installs/downloads, activation, merge or
push. This wave fixes the retained-command provenance finding only.

Confirmed the actual source path before editing production code:

- `dialogue_controller.reduce_dialogue` discards expired state and stale saved-row
  references before classifying/executing a query (lines 115–129).
- `DialogueRepository._apply_dialogue` persists that decision, but its former
  `if read_only or not agent_schema` skipped *all* command-link cleanup.
- The retained `command_update_id` then has no compatible retained continuation.
  `_command_origin` returns None; `assert_authorized_owner` correctly raises
  `PermissionError: Invalid retained command provenance` before worker recovery.
- Default legacy and agent command routes share this repository transition.

Minimal fix: read-only queries bypass new explicit-command replacement, **not**
the existing cleanup of absent/finished/incompatible continuations. Cleanup and
dialogue state persistence remain in the caller's transaction. A genuinely live
unchanged continuation, its original command origin, its TTL, and agent proposal
memory remain preserved. Owner assertion/provenance validation is unchanged.

## Tests and TDD evidence

Existing interpreter/reducer/repository/conversations are exercised without a
model. Tests use synthetic SQLite databases. NoAgent fails if the explicit
commands or their closed continuations unexpectedly invoke a model.

New coverage (16 tests):
- Both legacy and agent engines: expired, deleted/revised-reference, incompatible
  owned focus, and finished state followed by `/lista`; reopen before and after
  the query, validate owner, and replay the committed reply.
- Both engines: live `/anadir arroz` followed by `/lista` preserves state and TTL,
  then quantity 2 completes the original continuation.
- Both engines: injected completion failure proves the command link is cleared
  inside the transaction and both state/link roll back together.
- Product-query repository path: expired command permission is removed and a
  live command continuation remains unchanged after restart.

All commands used:

```powershell
$env:PYTHONPATH=(Get-Location).Path
$python='C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe'
& $python -m pytest tests/test_command_query_provenance.py -q
& $python -m pytest tests/test_command_query_provenance.py -q -k product_query
& $python -m pytest tests/test_command_query_provenance.py tests/test_agent_conversation.py tests/test_agent_storage.py tests/test_agent_recovery.py tests/test_recovery.py tests/test_dialogue_storage.py tests/test_dialogue_conversation.py tests/test_dialogue_end_to_end.py -q
& $python -m pytest -q
& $python -m ruff check .
git diff --check
```

### RED

- Before implementation, corrected command-query regression suite: **12 failed,
  2 passed in 2.31s**. Queries retained command 2 after discarding/incompatibly
  changing its state; rollback tests observed command 1 still present in the
  transaction. See `final-fix-red-corrected.txt`.
- Initial test draft mistakenly assumed `/producto` was a supported query
  command. It is not; removed that invalid command fixture. That initial run was
  **14 failed, 12 passed in 11.32s**, not counted as clean TDD evidence.
- Added product-query tests with the production fix temporarily reverted.
  First fixture `¿Hay arroz?` was not the supported query grammar and both passed;
  corrected to existing `¿Qué sabes de arroz?` grammar. Corrected RED:
  **1 failed, 1 passed, 14 deselected in 0.56s**, with the exact owner assertion
  `PermissionError: Invalid retained command provenance`. See
  `final-fix-product-red-corrected.txt`. Restored the same minimal fix afterward.

### GREEN / focused

- Initial corrected 14-test regression suite after implementation: **14 passed
  in 2.62s** (`final-fix-green.txt`).
- First expanded focused run: **1 failed, 175 passed in 54.20s**. New product-query
  test incorrectly expected no informational focus after an expired command.
  Existing reducer legitimately creates fresh query focus with no question;
  corrected the test to require that focus to reference query 2 and grant no
  continuation. No production behavior or oracle changed for that correction.
- Final focused run: **176 passed in 55.82s**, exit 0; no warnings.
  `final-fix-focused-final.txt`.

### Full suite / static checks

- Full pytest, foreground timeout **600000 ms**: **1218 passed in 404.37s**,
  exit 0, no warnings. `final-fix-full.txt`.
- Full-repository Ruff: **All checks passed!**, exit 0. `final-fix-ruff.txt`.
- `git diff --check`: exit 0. Git prints the normal Windows LF-to-CRLF advisory
  for the edited file; no whitespace errors.

## Real acceptance — repeated exactly, remains FAIL

Executed the current frozen real matrix twice in foreground after final source
and test changes. Explicit new safe output paths; refuses overwriting artifacts:

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:TEMP='C:/Users/Takeshi/AppData/Local/Temp/opencode'
$env:TMP=$env:TEMP
& $python -P scripts/probe_skills_agent.py --output docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl
& $python -P scripts/probe_skills_agent.py --output docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl
```

Both completed **exit 1 / acceptance FAIL**: each 50/53 real steps passed and
23/23 separately labelled simulated boundary steps passed. All real safety,
budget and complete-context checks pass; these do not override semantic FAIL.
The same three failures remain in both runs:

1. `explicit` update 2: wrong draft query for a saved-list question.
2. `internal_duplicate` update 3: missing separate-line decisions in completion.
3. `internal_duplicate` update 4: ensuing yes cannot complete the required flow.

No fifth hypothesis, prompt change, weakened oracle, or suppressed failing state.
Summary/all-case table/hash metadata:
`docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md`.
Compared every frozen metadata field to original `fix1-final-real-2.jsonl` and
between new runs: **no differences**. Probe metadata does not hash the root-level
dialogue_storage.py; final changed-source/test hashes are documented in the
summary without altering the frozen harness. Prior evidence is untouched.

## Files modified / added

Production (only): `dialogue_storage.py` (6 insertions, 4 deletions).

Tests: `tests/test_command_query_provenance.py` (new).

Evidence:
- `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl`
- `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl`
- `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md`

Report/verification under `.superpowers/sdd/2026-10-08-agente-skills-herramientas/`:
- `final-fix-report.md` (this file)
- `final-fix-red-corrected.txt`, `final-fix-product-red-corrected.txt`
- `final-fix-green.txt`, `final-fix-focused-final.txt`, `final-fix-full.txt`
- `final-fix-ruff.txt`, `final-fix-real-exits.txt`

## Self-review and remaining concerns

Read the final production/test diff: the schema-absence guard remains, explicit
command behavior is unchanged, queries cannot create a new command origin,
cleanup uses the existing key-scoped SQL, and no owner assertion or provenance
validator was removed/loosened. Tests protect cleanup omission, accidental live
permission/TTL loss, both engine paths, recovery/replay, and transaction rollback.
Existing slash-query proposal preservation tests also pass. No redesign.

**Explicit remaining blocker:** real semantic acceptance is still FAIL. Choosing
how to resolve saved-list versus draft queries and internal duplicate arguments
requires an architecture/product decision outside this assignment. Green tests
and this fixed storage finding are not acceptance/deployment approval. No further
prompt/model behavior attempt was made. Performance numbers are observations
only (the full suite ran concurrently); no load/unload or timing promise.
