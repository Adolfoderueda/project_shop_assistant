# Corrective report: original authenticated callback cancellation boundary

Status: DONE_WITH_CONCERNS. Local correction verified; independent review is
controller-owned and still pending. No activation/integration authorization implied.

## Scope and source

Work performed only in `C:/Users/Takeshi/Documents/projects/project_shop_assistant/.worktrees/guided-questions`.
Initial HEAD `9af83b07f01b80307e78286c3255ec8390218c85`, initially clean.
Read this task's brief first, then approved guided design sections 6–10.
Implementation commit: `157186b44ef2ffc644b13896165b5e6aeccae22c`
(`fix: bind guided history reset to original authenticated cancellation`).
This report and local synthetic verification outputs are a separate documentation commit.

No agents/reviewers spawned, controller ledger modified, private settings/DB read,
external network/Telegram calls, installation, real model probes, prompt/model/resource/default
changes, activation, worker restart, merge or push. Repository reopening in tests is
synthetic restart verification, not an operational restart.

## Root cause, evidence and dataflow

Symptom: after the delivered `one_each` choice was consumed and its resulting
review was delivered, consuming authentic `cancel` removed the pending proposal,
but old successful choices replayed under new update/query IDs remained eligible
history. Three replays filled the last-three-pair window with old review recipients.
The HTTP-context regression reproduced cancelled `huevos/carne/atun` descriptions
in the next bare `2` request, without any saved-list write.

Root cause: `_guided_history_boundary` restricted its durable inbox scan to
`kind='message'`. Genuine text `Cancelar` had an independently committed reset
boundary; genuine callback cancellation did not. Cancellation reduction and
proposal deletion were already correct. Replay idempotency was also correct:
`apply_guided_callback` intentionally returns the consumed token's cached result
without applying its transition again. The defect was inference-segment provenance,
not callback mutation or model decoding.

Trace: durable callback -> `_guided_token_row` (question/offer/index/token binding,
original consumer owner/source, committed result, delivery receipt) ->
`apply_guided_callback` -> typed `ResolvedChoice` -> reducer `cancel` ->
`_commit_guided` records consumer/result and removes proposal -> `guided_history`
boundary -> last three eligible pairs -> actual `GuidedOllamaAgent` HTTP messages.
Compared directly with genuine text reset and existing
`test_valid_successful_callback_replays_cannot_cross_real_reset_history_boundary`.

## Smallest fix and original-versus-replay authority

One production method changed: `_guided_history_boundary` now scans completed
events of both kinds. For callbacks it invokes the existing token provenance
validator before classification. Reset authority requires all of:

- persisted typed choice `kind == 'cancel'`, not button label or reply wording alone;
- `consumed_update_id == event.update_id`, identifying ORIGINAL consumption;
- existing validated original source/owner/offer/delivery/result chain;
- cancellation result equal to both original inbox reply and token result, with
  committed outbox/inbox agreement.

Only that original consumer's update ID is returned. A newer cached cancel replay
does not advance the boundary. The existing history pass still authenticates
replayed selections BEFORE excluding question origins at/before the boundary.
Thus corrupt cancelled-origin replays fail closed instead of being laundered by
their age. Unknown, missing/mismatched receipt, wrong-owner and rejected/corrupt
consumptions gain no authority. `keep_topic`/topic `no` preserve the main segment.
Exact text and slash-command boundary semantics, and the last-three-eligible-pair
limit, remain unchanged. No schema, reducer or mutation changes were needed.

## Regression coverage

New `tests/test_guided_callback_cancel_reset.py`: 17 synthetic cases, real repository,
controller/conversation/native decoder; mocks only HTTP and Telegram boundaries.

- Original delivered callback cancellation then 1/3 successful old-choice replays,
  repository reopening and empty authorized history.
- Saved IDs/revisions/quantities and original inbox/outbox rows unchanged by replays;
  no intermediate save.
- Fresh message context survives old cancel replay; actual fresh proposal also
  survives it and progresses through separately delivered final confirmation.
- Real DB result/outbox/token/receipt tampering and consumed rejection fail closed.
- Corrupt cancelled-origin replay is not hidden by the new boundary.
- Unknown callback with cancellation wording cannot grant reset authority.
- Unknown/missing/mismatched receipt/wrong-owner cancel attempts do not reset history.
- `keep_topic` callback and topic `no` are not global resets.
- Actual conversation captures next bare `2` HTTP request with no cancelled
  descriptions; synthetic clarification leaves no proposal and saved rows intact;
  subsequent genuine `arroz` request can be confirmed and saved once.

The HTTP fixture deliberately returns clarification for bare `2`. It proves the
authorized context passed to the real decoder, NOT intrinsic rejection of arbitrary
stale native suggestions. No artificial literal guard was introduced.

## Exact RED -> GREEN and final verification

All Python commands used existing root venv, safe-path `-P`, and
`$env:PYTHONPATH=(Get-Location).Path` in the worktree. Executable:
`C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe`.

RED (before production edit):

```powershell
$env:PYTHONPATH=(Get-Location).Path
& C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe -P -m pytest tests/test_guided_callback_cancel_reset.py -q *> .superpowers/sdd/2026-10-09-callback-cancel-reset/red.txt
```

Output: `4 failed, 11 passed in 3.51s`. Failures were both replay counts, fresh
context equality after cancel replay, and cancelled descriptions in actual HTTP
messages. All four failed on the intended assertions. Earlier fixture trial runs
exposed nonunique default query IDs and unacknowledged direct-ingest callbacks;
the synthetic fixture was corrected before the retained RED run. No production
change preceded that valid RED.

GREEN, same test command with output `green.txt`:
`15 passed in 8.20s`. Then added two existing-safety controls for corrupt old replay
and unknown callback wording; both passed in final focused/full runs.

Final focused command:

```powershell
& C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe -P -m pytest tests/test_guided_callback_cancel_reset.py tests/test_guided_final_fixes.py tests/test_guided_storage.py tests/test_guided_provenance.py tests/test_guided_conversation.py tests/test_guided_runtime.py -q *> .superpowers/sdd/2026-10-09-callback-cancel-reset/focused.txt
```

Output: `137 passed in 91.35s (0:01:31)`.

Full suite, run ONCE on final implementation/test state, tool timeout `1800000`:

```powershell
& C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe -P -m pytest -q *> .superpowers/sdd/2026-10-09-callback-cancel-reset/full.txt
```

Output: `1658 passed in 560.01s (0:09:20)`, exit 0, no skips/failures.
No source/test changes followed this full run.

Ruff:
`& C:/Users/Takeshi/Documents/projects/project_shop_assistant/.venv/Scripts/python.exe -P -m ruff check .`
-> `All checks passed!`, exit 0. Earlier scoped Ruff also passed.
`git diff --check` and precommit `git diff --cached --check`: no whitespace errors.
Git emitted only standard worktree LF-to-CRLF warnings.

## Files, self-review and remaining risks

Implementation files:
- `shopping_agent/guided_storage.py`: one minimal validated boundary branch.
- `tests/test_guided_callback_cancel_reset.py`: focused regressions/safety controls.
- `README.md`: narrow current-status clarification; archived v5 findings remain
  linked and historically true, local correction pending independent review.

Handoff files: this report plus `red.txt`, `green.txt`, `focused.txt`, `full.txt`.
Archived matrices/raw/freeze/hash evidence and historical final-fixes-v5 claims
were not rewritten or regenerated.

Self-review: inspected staged/source/new-test diffs, traced receipt/result/owner
guards through original consumption, checked cached replays cannot become reset
consumers, checked rejection/corruption paths, and verified current HTTP context
and fresh final confirmation. Existing exact text/slash/history tests pass.
The boundary scan now validates callback token chains outside the final three
pairs until the latest genuine reset; this deliberately fails closed on encountered
corrupt provenance and adds reads. No separate performance benchmark was run.

Remaining blockers are unchanged: independent review pending; real native v5
quality `42/102` bounded, `6/39` safety, `0/24` free; arbitrary stale model suggestions
from current untrusted input remain a general interpretation issue; installed-wheel
verification remains blocked; expiry-reset extra-turn UX expectations remain unmet.
No new real probes or package installation were authorized/performed. Synthetic
suite success is not native/Telegram acceptance. Do not activate or integrate.
