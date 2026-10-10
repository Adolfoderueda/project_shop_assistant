# Same final wave: source-only lifetime regression repair, evaluation v4

## INVALID EXPERIMENT — generation encoding error

V4 cannot count as acceptance or as an unchanged-case comparison. The generation
script used `read_text()` without explicit UTF-8 on Windows and misdecoded accented
v3 inputs (`sí` became `sÃ­`) before writing UTF-8 v4. Its equality assertion
compared against that same incorrectly decoded object. The unchanged-case claim
below is FALSE for v4, retained with this correction. Independent UTF-8 reads prove
v3/v4 cases differ. Original v2/v3 bytes are untouched. Offline v4 exit1:48/102
bounded,6/39 security,12/24 general;555executed63failed114unexecuted. Real v4 exit1:
20/102 bounded,3/39 security,0/24 general;333executed399unexecuted;249model turns,
111clarify18invalid1model_failure. These invalid-input results are NOT native-quality
comparisons. Preserve v4 bytes, disclose error, and use explicit UTF-8 plus independent
original-case comparison for the next matrix. No application/verifier/test/prompt
changes; no duplicate live run or polling. Full-suite notification still pending.

Independent `--matrix matrix-v4.json --verify {offline,real}-v4.jsonl` exit1,
summaries identical to execution:231offline/739real errors. This proves preserved
execution integrity, NOT input validity. Raw immutable hashes:
- offline4:19041235bytes SHA256 `6fa255c0f3669170cbf931f17ac7723deeba93f987e99c87d4e3a48e7c1fe704`.
- real4:10801061bytes SHA256 `89285d3acc0630a201879c4c4b67fca2e9cf0be4d89b6d11f830788e4566c820`.

Activation remains **BLOCKED**. This is not another fix wave, model change or prompt
iteration. After the original1631-test suite and v3 real/offline runs completed,
final self-review reproduced concrete finding1/2 lifetime bypasses. V3 was committed
as an explicitly blocked verified checkpoint `d026f0528e9a25f40c94dab4cfc61333864a6271`.
Its [complete native-quality/expiry/packaging results](final-fixes-v3.md) remain
historical, including every failure, all raw bytes and unchanged matrix expectations.

## Reproduced defects and narrow corrections

1. One or three legitimate cached callback replays AFTER a real Cancelar reintroduced
   the pre-reset summary into the last-three inference pairs. Three replays hid the
   reset event entirely. Now find the latest committed real reset/incompatible explicit
   command independently of the three-pair window. Validate successful token/receipt/
   result provenance first, then exclude pre-boundary question origins. Idempotent
   replay responses and audit survive; corrupt old replay provenance still fails closed.
2. `/lista` and `/estado` after legacy expiry let the legacy reducer delete its expired
   state, so the next bare2 could accept an injected stale arroz2 native proposal.
   Deterministic read commands now use existing apply_intent without reducing pending
   legacy memory. Invalid slash input while reset-required completes with the concrete
   reset notice, without revoking/clearing the expired recipient.
3. A successful `/quitar` history boundary must survive deletion of its referenced
   row. Reparsing against current rows may yield clarify: a committed incompatible
   explicit command still isolates inference history, but that history boundary alone
   NEVER authorizes clearing reset-required pending state. The state gate is separate.

No natural-language phrase catalogue, synthetic message, literal-citation authority,
new Choice/schema/framework, model/prompt/resource changes or extra permissions.
The independent freshness rule remains the CONTROLLER's conservative ruling under
the user-approved plan, not a directly user-approved UX change. Extra reset turn and
still-failed original convenience expectations must be disclosed, not waived.

### RED/GREEN

Existing venv `-P`, worktree PYTHONPATH. RED `-k valid_successful_callback_replays`
=>2failed27deselected0.78s. Expanded RED across final_fixes/acceptance
`-k 'valid_successful_callback_replays or corrupt_old_callback or read_or_invalid_slash or v3_exact_runtime'`
=>6failed1passed83deselected2.14s; corrupt old choice already failed closed.
Deleted-reference RED `-k successful_remove_command` =>1failed33deselected1.27s.
First expanded GREEN1failed113passed92.38s exposed that same boundary issue before
its fix. Final focused **263passed93.44s**, Ruff and diff clean.

## Exact archival integrity, including new packaged resources

Verifier v5 registers immutable v3 probe/runtime at the checkpoint commit above,
using the existing pinned local Git + per-newline bitmap reconstruction method.
`archive-v3.json` SHA256
`b89d9bfa91ce1a31cc7a45f58147780da8a7ca2c5a9d71e8b013f95098ef4566`.
All64recorded source/matrix/probe byte hashes, including new `migrations/__init__.py`,
must match reconstructed archived bytes. Raw v3 artifacts must match their registered
original hashes AND Git objects reconstructed with explicitly verified CRLF. No old
runtime or script hash exemption. Corrupted resource newline metadata fails; changed
raw native arguments fail both archive integrity and the independent native oracle.

Reverified v2 and v3 independently after these source changes:
- v2 original offline12errors/real906errors, recorded_runtime_verified=True.
- v3 offline36errors/real673errors, recorded_runtime_verified=True.
- The actual old failure counts/denominators remain unchanged; their scope is explicitly
  immutable archived execution, NOT current-source acceptance.
- Current v4 manifests must match current source/probe/matrix bytes exactly; they are
  not eligible for either historical registration. No silent unsafe fallback.

## Coherent freeze4 before rerunning final source

`acceptance-v4-freeze.json`, frozen2026-10-09T16:25:37.377028UTC:
- Matrix4 SHA256 `f0e34e29a1bd47fc5b760035d5d106fd62278e4bb07225980eb1ea997fdc1a63`.
- Verifier5/probe SHA256 `7947418626b1f932f815aaddce44799737bddcd4bcef86755a8549f06e9bd76b`.
- All28cases/55paths/165conversations/732steps remain value-identical to v3; original
  v2 expectations remain untouched. Repetitions3, fixed existing E4B, native-only,
  temperature0/thinkFalse/context8192/output512/context24000bytes/max4calls/max8tools.
- Runtime differences from v3: only guided_conversation.py and guided_storage.py.
  guided_ollama.py and all skill/prompt/schema/model/resource bytes are unchanged.

Original runs were finished before these new runs; no duplicate live suite/probe.
Final full-suite and full offline/real evaluation are running on frozen final source.
Actual outputs and separate independent verification will be appended after their
notifications, never inferred from earlier results.

Installed-wheel verification remains blocked: build/wheel/setuptools absent, no
installation permitted. Source resources/manifest tests do not establish a built or
installed wheel. Original Task7 native list/internal-duplicate acceptance stays open.
