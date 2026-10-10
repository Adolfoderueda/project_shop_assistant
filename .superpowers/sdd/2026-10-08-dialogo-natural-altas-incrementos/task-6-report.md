# Task6 implementation report

Status: DONE. REAL PASS, private Telegram acceptance remains pending.
Base: `0eb4f13`. Only Task6 probe/tests/docs/evidence modified; no runtime changes.

## Changes / coverage

Created opt-in `scripts/Probe-NaturalDialogue.ps1` with shared Python fallback and
`-P`, preflight existing loopback `/api/ps` + `/api/tags`, real OllamaInterpreter +
OllamaReplyWriter wrapped only for recording, Conversation/Repository/temp SQLite.
Offline fixtures replace HTTP only and are distinctly labelled. No fake real intent.
Transcribed exact A/B/C oracle before implementation. Six independent DBs:
A capture, B pending addition, C increment/no/yes, expiry900, reservation, revision.
Replay same confirmation update after30s and recreate Conversation between delta
and yes. Raw both model calls/status/timing, actual proposal, writer acceptance /
fallback, original input, expected/actual state+rows and deterministic labels emitted.
PASS requires compatible real proposals and drafts for add/increment/list plus all
writer acts; cannot pass on fallback alone. Error before measurement => ordersnull.

Subprocess tests execute actual PowerShell/Python exit0/1/2 and cleanup, audit a
private sentinel read (not merely unchanged bytes), inject local HTTP in REAL mode,
inspect intent requests for missing IDs/revisions/authority, reject incompatible
writer/purchase proposals, independently check exact A, B no premature avena,
C1+2=3, TTL after queries/greeting and replay advanced time/state/reply equality.
Migration/v1 prepared recovery is existing-suite coverage, not live probe coverage.
No private data, settingsload, Telegram, store calls, purchase requests, control of
user/bot processes, ACL, install, download, restart, unload, merge, push or subagents.
Reservation guard uses a synthetic reservation row with FK disabled and no order.

## Commands and exact relevant output

All Python invocations used shared `../../.venv/Scripts/python.exe` and `-P`, with
`$env:PYTHONPATH=$PWD.Path`. Subprocess tests deliberately override PYTHONPATH with
their isolated audited sitecustomize fixture; providers still execute real codecs.

RED before script existed:
```powershell
$env:PYTHONPATH=$PWD.Path; & ../../.venv/Scripts/python.exe -P -m pytest tests/test_natural_dialogue_probe.py -q
```
`7 failed in 0.59s`; PowerShell: `Probe-NaturalDialogue.ps1 ... -File no existe`.
Expected: every behavioral subprocess contract lacked the script, not imports.

Intermediate verification (retained here, not hidden):
- Same focused command: `6 failed, 1 passed in 2.53s`; embedded SQL double quotes
  lost by Windows PowerShell `-c`, SyntaxError line230. Replaced with single-quoted
  parameterized SQL (probe-only), no provider change.
- Same focused command: `1 failed, 6 passed in 81.27s`. Malicious-intent test expected
  C unchanged despite source-authorized increment with later explicit yes. Corrected
  test to assert no unauthorized orders, A/B unchanged and C only expected saves;
  source branch is the approved architecture, not model authorization.
- Strengthened advanced-clock replay test before implementation:
  `... -m pytest tests/test_natural_dialogue_probe.py::test_real_mode_does_not_substitute_interpreter -q`
  => `1 failed in 13.67s`, missing `now` field. Added advancing synthetic clock,
  state arithmetic/target check, B no TTL renewal and exact TTL900 guard.

GREEN focused (same first command): `7 passed in 68.25s (0:01:08)`.

REAL run1 (before strengthening clock, preserved):
```powershell
$env:PYTHONPATH=$PWD.Path; powershell.exe -NoProfile -File scripts/Probe-NaturalDialogue.ps1 -Python ../../.venv/Scripts/python.exe | Tee-Object -FilePath docs/superpowers/natural-dialogue-real-2026-10-08-run1.jsonl; Write-Output "PROBE_EXIT=$LASTEXITCODE"
```
Final JSON: `status=PASS,mode=REAL,failures=[],coverage=[add,increment,list],temporary_removed=true`;
`PROBE_EXIT=0`.34 steps,12 interpreter,33 accepted writer,0 fallback/orders.
PowerShell Tee originally UTF16; converted unchanged JSON lines to UTF8/BOM.

REAL final run2:
```powershell
$env:PYTHONPATH=$PWD.Path; powershell.exe -NoProfile -File scripts/Probe-NaturalDialogue.ps1 -Python ../../.venv/Scripts/python.exe | Out-File -Encoding utf8 docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl; Write-Output "PROBE_EXIT=$LASTEXITCODE"; Get-Content docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl -Tail 1
```
```text
PROBE_EXIT=0
{"status": "PASS", "mode": "REAL", "failures": [], "coverage": ["add", "increment", "list"], "temporary_removed": true}
```
34/34 steps,12 compatible interpreter requests,33/33 accepted writer requests,
0fallback/0orders. No real quality failure, schema defect or runtime repair observed.
Preserved run1 as preliminary rather than pretending static clock proves TTL.

Required full plain run, once before commit, timeout600000:
```powershell
$env:PYTHONPATH=$PWD.Path; & ../../.venv/Scripts/python.exe -P -m pytest
```
`collected 910 items`; `910 passed in 294.99s (0:04:54)`; exit0.
No filtering/skips/extra plugins; only existing anyio. Includes isolated stores/ACL,
runtime/recovery, v7-v8 migration/prepared v1, presentation and SQLite regressions.

```powershell
$env:PYTHONPATH=$PWD.Path; & ../../.venv/Scripts/python.exe -P -m ruff check .; git diff --check; git status --short
```
`All checks passed!`; diff check silent/exit0 (untracked additions also inspected).

## Files

- scripts/Probe-NaturalDialogue.ps1
- tests/test_natural_dialogue_probe.py
- docs/superpowers/prueba-dialogo-natural-2026-10-08.md
- docs/superpowers/natural-dialogue-real-2026-10-08-run1.jsonl
- docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl
- docs/setup.md; docs/superpowers/progress.md
- this report (no other plan/ledger modifications).

## Self-review / limits

Read full new-script diff and tests, verified raw replies A/B/C against approved
sequence rather than generating expectations from templates; no premature success,
social list query or lost rice variants. Read final staged diff before commit.
Both models genuinely returned outputs; facts/questions/options are application
owned. Model selects closed social/bullet/cancellation/composition variants, not
free prose. The source grammar also independently authorizes increment questions.
No provider outputs copied into production and no guards relaxed.
Existing loaded service used, first run latency includes19.500s first turn and does
not demonstrate cold start; run2 totals interpretation6.236439s / writer36.997373s /
steps48.186015s. A small sample is not a reliability or latency guarantee.
Private Telegram acceptance requires separate authorization; remains PENDING.

## Commit

Subject: `test: replay natural shopping conversations with real local Gemma`.
One task commit contains this report and the seven deliverable files above; its
SHA is returned to the controller after commit (avoids self-reference).
