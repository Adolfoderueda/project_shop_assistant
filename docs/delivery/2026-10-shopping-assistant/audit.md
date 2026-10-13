# Baseline audit — consolidated source review and release gates

Opened 2026-10-12 by Mushu; consolidated 2026-10-13 by Alpha. Independent reviewer: Izpi, [TAK-11](/TAK/issues/TAK-11). Work: [GitHub #5](https://github.com/Adolfoderueda/project_shop_assistant/issues/5) / [TAK-3](/TAK/issues/TAK-3), core [TAK-9](/TAK/issues/TAK-9). Tracking: #4. Draft [PR #11](https://github.com/Adolfoderueda/project_shop_assistant/pull/11). The dated paragraphs below retain their original historical status; the final reconciliation is at the end of this document.

## Baseline and approval reconciliation

Product baseline is remote `b9a29049160cc53737d1cb64a8138385aa2fedd2`; local planning HEAD `0594bf0247bcdef35656f2ead5bf3d054263e17b` is stale. Merged PR #3 includes native tools, guided questions, schema 9/10 and the callback reset repair. `runtime.py` routes opt-in `skills_agent` to native or guided conversation; default remains legacy. Do not recreate seven packages blindly or reuse migration 009. Named lists and reminders still require scoped changes. Full requirement-by-requirement P1 reconciliation remains pending.

The approved revision is preserved verbatim in `plan.md` (TAK-2 revision 2, `49708c36-dd46-4cf0-b496-4a49c14c7c55`). These observations supersede its historical code description; outcomes and gates are unchanged. No AGENTS.md or workflow existed among the baseline's 278 tracked paths. The shared checkout was not changed.

## Executed verification

Isolated clones, Python 3.12.10 and the existing project dependency environment. Synthetic databases and fake Telegram/model boundaries only. Browser tests use the existing Chromium binaries and fresh test profiles. Package build tools were installed only into disposable run scratch (`setuptools 84.0.0`, `wheel 0.48.0`); the wheel build itself used no index, build isolation or dependency downloads. No model download, private configuration, live Telegram, restart, purchase, merge or activation occurred.

| Check | Exact scope / result |
| --- | --- |
| Initial full baseline `python -m pytest -q` | Exit 1: **1616 passed, 42 failed**, 372.69s. 27 Chromium-path failures, 13 missing temporary-base failures, 2 archive-byte failures. No failures hidden or skipped. |
| Full baseline with existing Chromium path and synthetic legacy temporary base | Exit 1: **1656 passed, 2 failed**, 444.15s. Both failures are archived-evidence byte checks below. Source baseline unchanged. A checkout-index attempt did not rewrite already-present LF files; this run correctly remains RED. |
| Ruff on baseline and repaired candidate | `python -m ruff check .`, exit 0, all checks passed. |
| Baseline wheel | Build/install exit 0; installed `import storage` exit 1, missing `product_memory`. CLI `--help` alone passed and would miss this defect. Ten SQL resources and four skills are present. |
| Repaired wheel smoke | Exit 0: installed entry-path imports, skill loading, empty schema 10 and repeated migration. Source checkout excluded from module search. |
| Archive and migration focused tests | Exit 0: **4 passed**, 6.44s, including both previously failing archive tests. |
| Guided probe temporary directory | Synthetic audit-hook reproduction failed on hardcoded host path; platform-temp correction passed with actual temporary directory cleanup. |
| Staged diff | `git diff --cached --check`, exit 0 before implementation commit. |
| Windows CI | Workflow committed and actual run launched for `1c63ec11c8ada7652fe52a13daf34e75a0b7a7a5`: [run 38262453310](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38262453310). Checkout, setup, installs, Ruff and diff passed; the run was cancelled after 176 passing tests when concurrent staffing documentation commit `132e59c` superseded it. [Run 38263025076](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38263025076) started for that commit. This audit documentation commit will trigger the latest candidate run. **Final candidate CI is pending; CI is not yet established.** |

Both full baseline runs executed all 1658 tests. Passing a focused rerun does not make the unchanged baseline green, and no full repaired-candidate pass is claimed. The current CI run is the full candidate verification path. Full failure node IDs and portable commands are in [verification.md](verification.md).

## Reproducible findings

### P0-01 — HIGH: installed distribution cannot import storage (repair submitted)

`pyproject.toml` omits `product_memory` from explicit flat modules. `storage.py` and `dialogue_requests.py` depend on it. Build with `python -m pip wheel . --no-deps --no-build-isolation --no-index`; install into an empty target; outside the repository set `PYTHONPATH` to that target and run `python -P -c "import storage"`. Baseline raises `ModuleNotFoundError: No module named 'product_memory'`. Editable/source tests mask the defect.

Repair in `1c63ec1`: include that module and run `scripts/check_installed_wheel.py` against the installed target. RED then GREEN observed. No schema or product behavior changed. Independent review and final full candidate check remain pending. Tracked in #5 / PR #11.

### P0-02 — MEDIUM: frozen archive checks depend on local Git line endings (repair submitted)

Failures: `tests/test_guided_acceptance.py::test_archive_integrity_distinguishes_recorded_probe_from_current_verifier` and `::test_v3_exact_runtime_is_independently_archivable_without_hash_exemption`.

The four v2/v3 offline/real JSONL Git blobs contain LF, while immutable execution hashes describe CRLF. `verify_integrity` rejects the clean LF checkout as changed raw evidence. For all four, reconstructing CRLF matches the pre-existing expected SHA-256. The new local `.gitattributes` pins `text eol=crlf` for exactly those files; Git blobs, recorded hashes, matrices and expectations are unchanged. After materializing the declared checkout bytes, both tests pass. Existing objects for the pinned archive commits must be available, so CI fetches full Git history. Tracked in #5 / PR #11.

### P0-03 — MEDIUM: guided probe assumes Takeshi's Windows temporary path (repair submitted)

`scripts/probe_guided_questions.py` hardcoded `C:/Users/Takeshi/AppData/Local/Temp/opencode`. A host with another user cannot run synthetic acceptance reliably; it also ignores the run's temporary-directory boundary. An audit hook rejected actual `tempfile.mkdtemp` outside the platform temp root. Replacing the constant with `Path(tempfile.gettempdir())` passed the same synthetic one-each probe and cleanup check. Historical artifacts were not regenerated. The legacy PowerShell probes additionally require an existing `%LOCALAPPDATA%/Temp/opencode`; CI explicitly prepares that synthetic directory. Tracked in #5 / PR #11.

### P0-04 — HIGH release gate: native quality remains below documented acceptance

Historical native and guided evidence records semantic failures, not merely unavailable services. Native-agent execution status reports 50/53 steps on each of two runs, with saved-list query and internal-duplicate failures. Guided v5 reports 42/102 bounded, 6/39 security and 0/24 free conversations; many later steps were not reached. The subsequent callback-boundary fix has offline evidence but no new native acceptance. These are historical observations, not rerun results. Retain the no-activation gate and resolve quality under P1 with a reviewed interface/design before changing the native contract. No speculative prompt or model changes were made here.

### P0-05 — governance: CI and independent review still pending

Baseline has no workflows. Proposed Windows workflow now runs full offline tests, Ruff, diff and installed-wheel smoke without production credentials or model services. Setup follows [GitHub's Python workflow guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python). A completed actual run is required before calling CI established. Previous access checks reported unprotected default branch and 403 for protection/rulesets on this private account tier. No subscription/visibility change; manual independent-review and Takeshi merge gates remain.

## First-pass architecture observations

- Agent tools have no purchase/confirm tool, validate an entire native batch, permit one final mutator, and bind operations to a durable inbox snapshot. Agent storage atomically revalidates rows/reservations and commits list changes with the reply. Guided provenance/reducer/storage still needs the remaining detailed review.
- Telegram accepts authorized private sender/chat events, rejects forwarded/quoted provenance, stores inbox offsets durably and records delivered notices. Its documented at-least-once notices can duplicate after ambiguous send responses; do not promise exactly-once external delivery.
- SQL migrations 1–10 are versioned resources. They preserve immutable order snapshots and quarantine old checkout permissions; none creates named lists or reminders. Do not downgrade a schema-10 database to old code.
- All four public store adapters retain prepare/submit/reconcile/live_verified disabled. Product observations and incomplete shipping totals remain distinct from executable quotes. No current public-site price evidence was collected.
- Startup and task scripts require local configuration/consent. Runtime opens dedicated store profiles before recovery. Any future Telegram pilot must explicitly block checkout/recovery paths; dry_run is insufficient as a no-store-access policy.

## Remaining execution and review

Core-owner continuation on 2026-10-12: [CI run 38294353075](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38294353075/job/114961742907) completed successfully at PR head `de897e5a540819e447ca6cf457f59c3b2b17fef5`; see [verification.md](verification.md) for exact checks. Nine additional owned historical reports/continuation documents were read in full and their ledger entries updated. They preserve the earlier native 50/53 semantic failures and do not count as new model or Telegram verification. The remaining owned-path ledger, including large frozen JSONL evidence, remains incomplete; do not promote this PR to independent review yet.

Mushu continues on TAK-3: finish every pending path, complete the seven-package P1 reconciliation, verify/fix final CI, resolve material findings, and arrange an independent SHA-specific review when staffing is authorized. A proposed same-owner child was rejected by Paperclip's delegation-cycle rule; GitHub continuation #12 was closed as consolidated into #5. It is not a completed audit task or a blocker. No independent verdict or Takeshi acceptance has occurred.

This pass read 57 baseline paths in full and inspected selected sections of others. It did **not** complete the every-path audit. Automated test execution never counts as manual source review. Keep P0 open and P1's audit gate intact. Follow the task's scheduled CI monitor for the next execution window.

The 2026-10-12 continuation read three more owned historical paths in full: the command-provenance RED log, callback-reset RED log, and original native acceptance README. These are historical failures/evidence; they do not count as current test or model runs. The [documentation-head run 38296701619](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38296701619) at `3104459b30c0c5639239f41209a15298a293ef8a` failed its whitespace check before ACL, pytest or wheel. The exact commit diff added a stray carriage-return-only line to `acceptance.md`; PR-branch correction `a0954476e346ae9d1743dc4d9cf55278134d55c9` removes it. Fresh CI remains pending. Manual owned-path audit remains open.

## Path coverage

This inventory is a coverage ledger, not a claim that all paths were read. Review each pending path and record finding/test evidence before completing P0.

| Path | Review status |
| --- | --- |
| .gitignore | Source read; first-pass review, independent QA pending |
| .superpowers/sdd/2026-09-27-asistente-compras/final-fix-report.md | Source read; historical offline result and live limits, independent QA pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/final-fix-report.md | Source read; historical offline result and live limits, independent QA pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/task-1-report.md | Source read; historical Ollama adapter evidence, independent QA pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/task-2-report.md | Source read; historical provider routing and lock evidence, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-focused-final.txt | Source read; historical 176 focused passes, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-full.txt | Source read; historical 1218 full-suite passes, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-green.txt | Source read; historical 14 focused passes, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-product-red-corrected.txt | Source read; historical 1 failed/1 passed command provenance RED, expired permission failed closed on restart |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-real-exits.txt | Source read; both historical real probes exit 1, release gate retained |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-red-corrected.txt | Source read, all 639 lines; historical RED capture (12 failed, 2 passed) for command-query provenance and rollback failpoints. Later repair/tests supersede this baseline failure; no current execution. |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-report.md | Source read; retained command provenance repair and repeated 50/53 real semantic failures, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-ruff.txt | Source read; historical Ruff success, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-5-report.md | Source read; bounded native loop and HTTP/tool validation claims are historical, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-6-report.md | Source read; opt-in integration and durable discard notice history, independent QA pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-7-report.md | Source read; 50/53 final real steps with saved-list and duplicate failures remain release gates |
| .superpowers/sdd/2026-10-08-dialogo-natural-altas-incrementos/task-6-report.md | Source read; historical isolated real-model probe and Telegram limit, independent QA pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/focused.txt | Source read; historical 137 focused passes, independent QA pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/full.txt | Source read; historical 1658 full-suite passes, independent QA pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/green.txt | Source read; historical 15 focused passes, independent QA pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/red.txt | Source read; historical 4 failed/11 passed callback reset RED, stale cancelled context leaked into replay/history |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/report.md | Source read; callback reset provenance and historical 1658 offline passes, independent QA pending |
| README.md | Source read; first-pass review, independent QA pending |
| catalog.py | Source read; first-pass review, independent QA pending |
| checkout.py | Source read; first-pass review, independent QA pending |
| checkout_storage.py | Source read; reservation, attempt and reconciliation boundaries first-pass review, independent QA pending |
| cli.py | Source read; doctor and local-switch boundaries first-pass review, independent QA pending |
| config.py | Source read; first-pass review, independent QA pending |
| conversation.py | Source read; legacy inbox recovery and model boundary first-pass review, independent QA pending |
| dialogue.py | Source read; bounded state, TTL and closed answer grammar first-pass review, independent QA pending |
| dialogue_additions.py | Source read; duplicate and missing-quantity transition first-pass review, independent QA pending |
| dialogue_controller.py | Source read; stale/reserved reference and confirmation reducer first-pass review, independent QA pending |
| dialogue_increments.py | Source read; selected increment references and confirmation first-pass review, independent QA pending |
| dialogue_replies.py | Source read; persisted-result reply first-pass review, independent QA pending |
| dialogue_requests.py | Source read; whole-message grammar and proposal guard first-pass review, independent QA pending |
| dialogue_storage.py | Source read; transactional reducer, target revisions and dialogue provenance first-pass review, independent QA pending |
| docs/setup.md | Source read; Windows setup, owner binding, worker lock, ACL, offline probes, optional Ollama and opt-in startup guidance keep live Telegram/private access gated. Its dated `gemma4:e2b` examples describe legacy experiments, not current E4B acceptance; no commands were executed from this guide. |
| docs/store-capabilities.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/continuacion-gemma-2026-10-01.md | Source read; historical quality and ACL work, private Telegram gate remains |
| docs/superpowers/continuacion-gemma-lista-2026-09-30.md | Source read; historical list/card implementation and quality limits, independent QA pending |
| docs/superpowers/continuacion-telegram-2026-09-28.md | Source read; historical user-reported Telegram activity, no current pilot or restart evidence |
| docs/superpowers/evidence/2026-10-08-skills-agent/README.md | Source read; historical original real 31/53 in both frozen passes, fix-round real 50/53 with three failures; no new real acceptance |
| docs/superpowers/evidence/2026-10-08-skills-agent/execution-status.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 73 step passes/3 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 73 step passes/3 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md | Source read; confirms 50/53 real steps in each frozen run and three semantic failures; independent QA pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix-round-1.md | Source read; historical Task 7 fix round records two real 50/53 runs with saved-query and internal-duplicate failures; offline and focused tests do not close native quality. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-offline.jsonl | Source read by full 78-record JSONL parse; historical 0 real E4B and 76 simulated steps, 76 step passes/0 failures; archived summary PASS / quality NOT_TESTED. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-1.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 73 step passes/3 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-2.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 73 step passes/3 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-control.jsonl | Source read by full 66-record JSONL parse; historical 30 real E4B and 35 simulated steps, 35 step passes/30 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-recipe.jsonl | Source read by full 66-record JSONL parse; historical 30 real E4B and 35 simulated steps, 55 step passes/10 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-control.jsonl | Source read by full 16-record JSONL parse; historical 15 real E4B and 0 simulated steps, 0 step passes/15 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-full-real.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 73 step passes/3 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-recipe.jsonl | Source read by full 16-record JSONL parse; historical 15 real E4B and 0 simulated steps, 15 step passes/0 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-contract.jsonl | Source read by full 66-record JSONL parse; historical 30 real E4B and 35 simulated steps, 60 step passes/5 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-control.jsonl | Source read by full 66-record JSONL parse; historical 30 real E4B and 35 simulated steps, 55 step passes/10 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-contract.jsonl | Source read by full 76-record JSONL parse; historical 30 real E4B and 45 simulated steps, 65 step passes/10 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-control.jsonl | Source read by full 76-record JSONL parse; historical 30 real E4B and 45 simulated steps, 65 step passes/10 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-full-real.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 70 step passes/6 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-scope.jsonl | Source read by full 66-record JSONL parse; historical 30 real E4B and 35 simulated steps, 60 step passes/5 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-schema-only-real.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 63 step passes/13 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-1.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 54 step passes/22 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-2.jsonl | Source read by full 78-record JSONL parse; historical 53 real E4B and 23 simulated steps, 54 step passes/22 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/offline.jsonl | Source read by full 78-record JSONL parse; historical 0 real E4B and 76 simulated steps, 76 step passes/0 failures; archived summary PASS / quality NOT_TESTED. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/real-pass-1.jsonl | Source read by full 69-record JSONL parse; historical 53 real E4B and 14 simulated steps, 41 step passes/26 failures; archived summary FAIL / quality FAIL. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/schema-diagnostic.jsonl | Source read by full 10-record JSONL parse; historical 8 real E4B and 0 simulated steps, 4 step passes/4 failures; diagnostic or micro sample, no full-suite verdict. Not current acceptance. |
| docs/superpowers/evidence/2026-10-08-skills-agent/skill_micro_probe.py | Source read; five fresh real local-model contexts per case after simulated setup, no current execution or broad acceptance |
| docs/superpowers/evidence/2026-10-08-skills-agent/verification.txt | Source read; original 1195-test offline pass and repeat 31/53 real failures are historical, no current quality acceptance |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/.gitattributes | Source read; two archived quality files retain CR-aware whitespace attributes, no evidence bytes changed |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/preregistration.json | Source read as complete structured JSON (178911 checkout bytes); seven preregistered cases, 18 calls and one ablation factor. Historical design, not a quality pass. |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/results.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/trials.jsonl | Source read by full 18-record JSONL parse; historical ablation trial: 5/18 semantically correct, 8/18 native valid, 10/18 safe fallback. No general repair or acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v3-freeze.json | Source read; historical v3 freeze records bounded native evaluation inputs and activation gate, not a current pass. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v4-freeze.json | Source read; historical v4 freeze adds reset and expiry cases; later evidence invalidates its unchanged-input comparison. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v5-freeze.json | Source read; historical v5 freeze records explicit UTF-8 correction and independently compared case values. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v2.json | Source read; historical v2 byte reconstruction and hash inventory only, not current-source acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v3.json | Source read; historical v3 byte reconstruction and hash inventory only, not current-source acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/execution-status.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v3.md | Source read; historical v3 offline 102/102 bounded, but real-model 41/102 bounded, 6/39 security and 0/24 general; the record also reports model/backend errors and a later callback-replay regression. Activation remained blocked; no result rerun here. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v4.md | Source read; reports callback replay and expiry bypass fixes with focused 263-pass evidence, but declares v4 native comparison invalid due to Windows encoding and activation blocked. Historical claims unrerun. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v5.md | Source read; corrected UTF-8 v5 remains blocked: real 42/102 bounded, 6/39 security, 0/24 general; final review reports HIGH callback-cancellation history residual. Historical results, not rerun here. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/handoff.md | Source read in full (5626 bytes); historical callback Cancelar repair at 157186b, 1658-test offline report and explicit pending native/Telegram acceptance. Claims not rerun here. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json | Source read by structured 28-case/124-step review and full revision diff; adds explicit-reset security cases. Frozen synthetic expectations are inputs, not execution results. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v4.json | Source read by structured 28-case/124-step review and full revision diff; its UTF-8 text became mojibake despite the note claiming unchanged cases. Historical v4 real comparison is invalid. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v5.json | Source read by structured 28-case/124-step review and full revision diff; restores parsed case/parameter values equal to v3 while changing version/note. This corrects matrix text, not E4B quality. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix.json | Source read; frozen v2 input matrix defines 26 cases with three repetitions covering button/text routes, duplicate and mixed edits, expiry, replay, reservation, unknown base and queries. Inputs and expected state are not execution results. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1-source.txt | Source read; frozen synthetic-input A/B script varied tool descriptions and captured raw local model calls; no current probe run |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1.jsonl | Source read by full 11-record JSONL parse; historical native diagnostic HTTP calls, no scenario acceptance or current quality claim. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v2.jsonl | Source read by full 8-record JSONL parse; historical native diagnostic HTTP calls, no scenario acceptance or current quality claim. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v2.jsonl | Source read by full 673-record JSONL parse; historical offline-fixture conversations: bounded 102/102, security 24/27, general-free 24/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v3.jsonl | Source read by full 733-record JSONL parse; historical offline-fixture conversations: bounded 102/102, security 30/39, general-free 24/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v4.jsonl | Source read by full 733-record JSONL parse; historical offline-fixture conversations: bounded 48/102, security 6/39, general-free 12/24. V4 matrix text is encoding-damaged, so its comparison is invalid. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v5.jsonl | Source read by full 733-record JSONL parse; historical offline-fixture conversations: bounded 102/102, security 30/39, general-free 24/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v2.jsonl | Source read by full 673-record JSONL parse; historical real-model conversations: bounded 6/102, security 6/27, general-free 0/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v3.jsonl | Source read by full 733-record JSONL parse; historical real-model conversations: bounded 41/102, security 6/39, general-free 0/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v4.jsonl | Source read by full 733-record JSONL parse; historical real-model conversations: bounded 20/102, security 3/39, general-free 0/24. V4 matrix text is encoding-damaged, so its comparison is invalid. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v5.jsonl | Source read by full 733-record JSONL parse; historical real-model conversations: bounded 42/102, security 6/39, general-free 0/24. Unexecuted steps stay failures; no Telegram acceptance. |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/results.md | Source read; initial guided acceptance reports real 6/102 bounded, 6/27 security, 0/24 general and expired antecedent defect; archived verification cannot establish current acceptance. |
| docs/superpowers/gemma4-12b-local-2026-10-10.md | Source read; model download and 12B comparison paused by user, no model-access claim |
| docs/superpowers/natural-dialogue-real-2026-10-08-run1.jsonl | Source read by full 39-record JSONL parse; historical 34-step synthetic-DB e2b run summary PASS. No current native-agent quality or Telegram evidence. |
| docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl | Source read by full 39-record JSONL parse; historical 34-step synthetic-DB e2b run summary PASS. No current native-agent quality or Telegram evidence. |
| docs/superpowers/natural-dialogue-real-2026-10-08-run3.jsonl | Source read by full 39-record JSONL parse; historical 34-step synthetic-DB e2b run summary PASS. No current native-agent quality or Telegram evidence. |
| docs/superpowers/plans/2026-09-27-asistente-compras.md | Source read; older broad shopping plan documents durable inbox/outbox and checkout controls. Its paid-model and purchase scope is historical and does not authorize either under the approved P0 plan. |
| docs/superpowers/plans/2026-09-29-gemma4-local-telegram.md | Source read; older local-model route gives commands priority and keeps Ollama on loopback; private Telegram activation remains a separate gate. |
| docs/superpowers/plans/2026-09-29-lista-fichas-gemma.md | Source read; older product-memory plan separates dated observations and idempotent research backlog from live prices or store purchases. |
| docs/superpowers/plans/2026-10-01-conversacion-contextual-gemma.md | Source read; historical six-task contextual dialogue plan defines 15-minute state TTL, owner-bound source references, exact product matching, atomic inbox/list/outbox mutations and confirmation before replacement. Its v6/current-schema and old worktree instructions are historical. |
| docs/superpowers/plans/2026-10-08-agente-skills-herramientas.md | Source read; seven-package contract specifies fixed seven tools, application-owned confirmation and 15-minute expiry, atomic SQLite writes, bounded local E4B loop, opt-in routing and synthetic/real probes. Its historical subagent workflow is superseded by Paperclip ownership; source and live-quality review remain open. |
| docs/superpowers/plans/2026-10-08-dialogo-natural-altas-incrementos.md | Source read; historical six-task plan specifies source-grounded greeting/add/increment, 900-second pending-state TTL, stale-base confirmation refusal, v1 presentation recovery, and offline/real-model probe separation. Its old worktree/subagent instructions are historical context, not this delivery route. |
| docs/superpowers/plans/2026-10-08-respuestas-naturales-gemma.md | Source read; historical presentation plan separates transactional prepare/finalize from local HTTP drafting, preserves command/purchase routes, validates grounded fact/option tokens and recovers prepared replies without replaying mutations. Its former subagent workflow is superseded by Paperclip ownership; model prose still needs independent quality evidence. |
| docs/superpowers/plans/2026-10-09-preguntas-guiadas-telegram.md | Source read; historical eight-task guided plan requires application-owned scope and confirmation, v10 typed events/delivery receipts, single-use callbacks, bounded E4B, opt-in rollback and separate real/Telegram acceptance. Its old agent/worktree execution instructions are superseded by Paperclip ownership. |
| docs/superpowers/progress.md | Source read; chronological historical test/model/store claims and explicit Telegram gates reviewed. The 2026-10-12 heading still says candidate CI pending even though later PR heads passed; treat that line as dated, not current CI status. |
| docs/superpowers/prueba-dialogo-contextual-2026-10-01.md | Source read; historical two corrected real probes each 25/25 after earlier 13/25 failures; synthetic DB and no Telegram acceptance or general reliability proof. |
| docs/superpowers/prueba-dialogo-natural-2026-10-08-run3.md | Source read; historical natural-dialogue 34/34 real steps, distinct from native-agent quality and Telegram acceptance |
| docs/superpowers/prueba-dialogo-natural-2026-10-08.md | Source read; historical two isolated real-model passes each 34/34 with six synthetic DBs and no private Telegram; narrow sample does not close current native-agent quality. |
| docs/superpowers/prueba-gemma-2026-10-01.md | Source read; historical ten-message Gemma probe found product-query and offer-intent quality failures, no current model test |
| docs/superpowers/prueba-respuestas-gemma-2026-10-08.md | Source read: dated e2b reply-writer evidence preserves initial 0/18 normal-draft failures and the later conditioned-schema 18/18 accepted in each of two synthetic 20-scenario runs. Application facts and choices remain fixed, and two injected errors fall back; historical local-model success is neither E4B semantic quality nor private Telegram acceptance. |
| docs/superpowers/specs/2026-09-27-asistente-compras-design.md | Source read; older approved buying design requires exact restricted-product identity, durable order recovery, and separate real-purchase authorization. Current MVP plan excludes payments; no buy capability inferred. |
| docs/superpowers/specs/2026-09-29-gemma4-local-telegram-design.md | Source read; approved local-model design preserves command priority, loopback-only Ollama, deterministic mutation and separate live Telegram acceptance. Historical provider options are not current spend authorization. |
| docs/superpowers/specs/2026-09-29-lista-fichas-gemma-design.md | Source read; approved list/product-card design keeps SQLite facts and dated public observations, idempotent research backlog, no model authority for purchase or SQL, and real-model/live acceptance gate. |
| docs/superpowers/specs/2026-10-01-conversacion-contextual-gemma-design.md | Source read; historical contextual-dialogue contract binds focus and one question to authorized chat with 15-minute expiry, revision checks, atomic inbox/list/outbox and explicit replacement confirmation. No contextual permission for purchase or private-bot activation. |
| docs/superpowers/specs/2026-10-08-agente-skills-herramientas-design.md | Source read; confirmation, tool and acceptance contracts reconciled above; independent QA pending |
| docs/superpowers/specs/2026-10-08-dialogo-natural-altas-incrementos-design.md | Source read; historical natural-dialogue contract keeps incomplete adds outside saved lines, requires base-plus-delta confirmation for increments, rejects greetings as list requests, and preserves replay/revision guards. Design approval was not deployment approval. |
| docs/superpowers/specs/2026-10-08-respuestas-naturales-gemma-design.md | Source read; approved writer design requires application-owned immutable facts, durable prepared/final reply, replay without duplicate mutations, and safe fallback; design approval alone did not authorize activation. |
| docs/superpowers/specs/2026-10-09-preguntas-guiadas-telegram-design.md | Source read; guided contract requires durable typed questions, provenance, single-use callback tokens, delivered full-summary witness and renewed confirmation after edits. Historical free-dialogue probes included 0/15 complete conversations; offline green alone cannot close its real-model or Telegram gate. |
| docs/superpowers/task-8-report.md | Source read; historical checkout crash-recovery fake confirms one submit, private Telegram and live purchase gates remain closed |
| domain.py | Source read; strict shared event/list/reply contracts first-pass review, independent QA pending |
| interpreter.py | Source read; command authorization and untrusted interpreter boundary first-pass review, independent QA pending |
| migrations/001.sql | Source read; first-pass review, independent QA pending |
| migrations/002.sql | Source read; first-pass review, independent QA pending |
| migrations/003.sql | Source read; first-pass review, independent QA pending |
| migrations/004.sql | Source read; first-pass review, independent QA pending |
| migrations/005.sql | Source read; first-pass review, independent QA pending |
| migrations/006.sql | Source read; first-pass review, independent QA pending |
| migrations/007.sql | Source read; first-pass review, independent QA pending |
| migrations/008.sql | Source read; first-pass review, independent QA pending |
| migrations/009.sql | Source read; first-pass review, independent QA pending |
| migrations/010.sql | Source read; first-pass review, independent QA pending |
| migrations/__init__.py | Source read; first-pass review, independent QA pending |
| offers.py | Source read; first-pass review, independent QA pending |
| ollama_interpreter.py | Source read; local endpoint, bounded schema and source validation first-pass review, independent QA pending |
| ollama_replies.py | Source read; closed draft schema and deterministic validation first-pass review, independent QA pending |
| presentation.py | Source read; versioned snapshot/public context first-pass review, independent QA pending |
| presentation_phrases.py | Source read; closed phrase composition first-pass review, independent QA pending |
| presentation_replies.py | Source read; facts, pending questions and historical-price wording first-pass review, independent QA pending |
| presentation_storage.py | Source read; presentation job and outbox transaction first-pass review, independent QA pending |
| presentation_validation.py | Source read; token coverage and application-owned fact substitution first-pass review, independent QA pending |
| product_memory.py | Source read; first-pass review, independent QA pending |
| pyproject.toml | Source read; first-pass review, independent QA pending |
| recovery.py | Source read; first-pass review, independent QA pending |
| requirements.lock | Source read; 27 pinned runtime/test dependencies, existing lock retained |
| restrictions.py | Source read; first-pass review, independent QA pending |
| runtime.py | Source read; first-pass review, independent QA pending |
| scripts/Install-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Probe-Dialogue.ps1 | Source read; synthetic legacy dialogue matrix, optional loopback Ollama and approved temp-base requirement; not run in this audit |
| scripts/Probe-NaturalDialogue.ps1 | Source read: opt-in synthetic dialogue probe separates offline fake-HTTP cases from existing loopback e2b model checks; confirms addition/increment, expiry, replay and zero orders, with PASS/FAIL/PENDING exits. Historical e2b results do not satisfy E4B or Telegram acceptance. |
| scripts/Probe-Replies.ps1 | Source read: opt-in writer probe uses invented SQLite scenarios and fake interpreter, with offline draft/rejection paths and optional existing loopback e2b writer; verifies prepared presentation, transaction/HTTP separation, durable replay and zero orders. Offline rejection does not prove semantic reply quality. |
| scripts/Start-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Stop-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Uninstall-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/diagnose_guided_native_v2.py | Source read; diagnostic contrasts guided prompt with existing skills using three synthetic inputs and local Ollama; not executed in this audit |
| scripts/probe_guided_questions.py | Source read; stdlib verifier compares frozen matrix expectations, raw native envelopes, delivered-review facts and transport receipts, rejects altered archived source bytes, and labels offline fixtures separately from real E4B. Execution uses synthetic SQLite/FakeBot; no probe was run in this audit batch. |
| scripts/probe_skills_agent.py | Source read; synthetic 19 natural and 7 boundary cases assert tool choice, argument/state/reply safety, atomic batch/replay and context budgets; offline HTTP is explicitly simulated and missing E4B returns PENDING. Its oracle does not convert safe fallback into semantic PASS. No probe was run in this audit batch. |
| shop_assistant/__init__.py | Source read; first-pass review, independent QA pending |
| shop_assistant/__main__.py | Source read; first-pass review, independent QA pending |
| shopping_agent/__init__.py | Source read; first-pass review, independent QA pending |
| shopping_agent/contracts.py | Source read; strict proposal and model boundary first-pass review, independent QA pending |
| shopping_agent/conversation.py | Source read; first-pass review, independent QA pending |
| shopping_agent/guided_contracts.py | Source read; guided ownership, provenance and witness models first-pass review, independent QA pending |
| shopping_agent/guided_controller.py | Source read; question identity, delivered review witness and guarded confirmation first-pass review, independent QA pending |
| shopping_agent/guided_conversation.py | Source read; event routing and callback boundary first-pass review, independent QA pending |
| shopping_agent/guided_ollama.py | Source read; bounded one-call native candidate and untrusted history first-pass review, independent QA pending |
| shopping_agent/guided_replies.py | Source read; application-owned review rendering first-pass review, independent QA pending |
| shopping_agent/guided_storage.py | Source read; choice receipts, delivered-review witness and atomic guarded writes first-pass review, independent QA pending |
| shopping_agent/ollama.py | Source read; first-pass review, independent QA pending |
| shopping_agent/proposals.py | Source read; control, expiry and revalidation first-pass review, independent QA pending |
| shopping_agent/replies.py | Source read; deterministic full review text first-pass review, independent QA pending |
| shopping_agent/skills.py | Source read; first-pass review, independent QA pending |
| shopping_agent/skills/altas.md | Source read; first-pass review, independent QA pending |
| shopping_agent/skills/cambios.md | Source read; first-pass review, independent QA pending |
| shopping_agent/skills/consultar.md | Source read; first-pass review, independent QA pending |
| shopping_agent/skills/propuestas.md | Source read; first-pass review, independent QA pending |
| shopping_agent/storage.py | Source read; first-pass review, independent QA pending |
| shopping_agent/tools.py | Source read; first-pass review, independent QA pending |
| storage.py | Source read; schema/owner/inbox/outbox and legacy mutation first-pass review, independent QA pending |
| stores/__init__.py | Source read; first-pass review, independent QA pending |
| stores/amascotados.py | Source read; first-pass review, independent QA pending |
| stores/base.py | Source read; first-pass review, independent QA pending |
| stores/browser.py | Source read; first-pass review, independent QA pending |
| stores/charro.py | Source read; first-pass review, independent QA pending |
| stores/connections.py | Source read; first-pass review, independent QA pending |
| stores/mercadona.py | Source read; first-pass review, independent QA pending |
| stores/nappy.py | Source read; first-pass review, independent QA pending |
| stores/public.py | Source read; first-pass review, independent QA pending |
| stores/registry.py | Source read; first-pass review, independent QA pending |
| telegram_io.py | Source read; first-pass review, independent QA pending |
| tests/__init__.py | Source read; first-pass review, independent QA pending |
| tests/agent_support.py | Source read; pure synthetic message, line and snapshot factories supply fixed identities/time and do not exercise persistence or a model. |
| tests/dialogue_support.py | Source read; temporary SQLite helpers drive the real Conversation and disable store/checkout operations in dialogue integration. Their fake interpreter does not prove real-model understanding. |
| tests/factories.py | Source read; synthetic message, intent and offer factories; offer timestamp uses the test clock at construction and is not a current public-price observation. |
| tests/fakes.py | Source read; fake Telegram/OpenAI/store boundaries, including a simulated purchase ledger and lost-response path. `live_verified=True` is a test fixture capability, not evidence of any live adapter or purchase authorization. |
| tests/fixtures/stores/amascotados.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/fixtures/stores/charro.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/fixtures/stores/mercadona-search.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/fixtures/stores/mercadona.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/fixtures/stores/nappy-out.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/fixtures/stores/nappy.html | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/guided_helpers.py | Source read; guided fixtures use temporary SQLite, synthetic callback tokens/delivery digests, purchase-blocking test adapters and fake HTTP envelopes. They cover test inputs, not real E4B or Telegram acceptance. |
| tests/stores/test_amascotados.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_browser.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_charro.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_contract.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_mercadona.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_nappy.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/stores/test_public_adapters.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/test_agent_contracts.py | Source read; strict quantities, authority-free model args, bounded items, complete review and proposal lifetime cases |
| tests/test_agent_conversation.py | Source read; command-route precedence, durable replay, greeting preservation, rollback and model-prose discard cases |
| tests/test_agent_end_to_end.py | Source read; HTTP-simulated end-to-end boundaries, explicit confirmation and conflict cases; no real-model quality claim |
| tests/test_agent_ollama.py | Source read; bounded E4B calls, strict envelopes, fail-closed model errors, fact preservation, context limits and cancellation cases |
| tests/test_agent_probe.py | Source read; private-path isolation, unavailable versus pass, honest action/reply oracles and expiry edge cases |
| tests/test_agent_proposals.py | Source read; pure reducer guards for ambiguity, quantity arithmetic, revision/owner changes, expiry and duplicate conflicts |
| tests/test_agent_recovery.py | Source read; restart replay, v8-to-v10 preservation, outbox rollback, legacy-job priority and post-commit ambiguity cases |
| tests/test_agent_replies.py | Source read; full deterministic review, no pre-commit success, oversize refusal and application-fact rendering cases |
| tests/test_agent_route_notices.py | Source read; opt-in rollback notice persistence, transaction rollback, private recipient and replay cases |
| tests/test_agent_runtime.py | Source read; opt-in engine construction, worker lock, disable revocation and synthetic settings-read cases |
| tests/test_agent_skills.py | Source read; fixed packaged skills and MIT attribution assertions; no live model coverage |
| tests/test_agent_storage.py | Source read; atomic batch rollback, durable review witness, stale/foreign/expired refusal, replay and command provenance cases |
| tests/test_agent_tools.py | Source read; seven strict tools, whole-batch validation, message binding, stale read and untrusted product-title cases |
| tests/test_checkout.py | Source read; fake-store and temporary SQLite cases cover quote/revision invalidation, reservation allocation, uncertain or failed submit, durable recovery, unverified carts and snapshot no-rebuy. No real purchase. |
| tests/test_command_query_provenance.py | Source read; temporary SQLite tests cover command-permission cleanup after expired, deleted, revised, incompatible or finished dialogue on read-only queries, preservation of live permission/TTL, rollback and restart for legacy and agent routes. |
| tests/test_conversation.py | Source read; temporary SQLite with fake interpreter and mocked provider covers owner-scoped quantity confirmation, stale/replayed decisions, command priority, source grounding, product observations and no model purchase authority. No real inference. |
| tests/test_dialogue.py | Source read; pure dialogue contracts enforce 900-second expiry, offered-choice vocabulary, quantity/selection scoping, unsupported-unit refusal and no model purchase authority. Temporary repository helper also reviewed. |
| tests/test_dialogue_conversation.py | Source read; temporary SQLite and fake interpreter/HTTP cases cover source-grounded focus, duplicate selection, expiry/replay, stale rows, model outage and no destructive model authority. No real inference. |
| tests/test_dialogue_end_to_end.py | Source read; fake Telegram Bot and temporary SQLite exercise runtime restart/outbox replay, expiry, foreign chat, model failure fallback and transaction rollback. Windows offline probe is asserted by a test but was not run in this audit batch. |
| tests/test_dialogue_increments.py | Source read; isolated SQLite cases require selection, base/delta/total confirmation, stale/reserved refusal, overflow/units refusal, rollback/replay and prepared v1 result recovery. No live model evidence. |
| tests/test_dialogue_quantity_bounds.py | Source read; SQLite max-integer and overflow cases cover contextual answers, commands, model proposals, state contracts and replay without list changes. |
| tests/test_dialogue_replacement.py | Source read; synthetic SQLite cases require explicit source/destination/quantity and duplicate confirmation, reject stale/reserved rows, preserve prior order snapshots and roll back failed writes. |
| tests/test_dialogue_requests.py | Source read; source-grounded greeting/list/increment grammar and constrained Ollama schema tests reject incompatible model proposals and preserve explicit command priority. HTTP is mocked. |
| tests/test_dialogue_storage.py | Source read; synthetic v5-to-v10 migration preservation, stale clarification removal, 900-second state expiry, owner/source binding and transaction rollback tests. No private database tested. |
| tests/test_end_to_end.py | Source read; fake Bot/Store offline cycles cover restart, simulated receipts, uncertain submit and recovery without duplicate submit. The test's live mode still uses FakeStore, not a real purchase. |
| tests/test_guided_acceptance.py | Source read; independent offline verifier fixtures reject forged native tool envelopes, relaxed schemas, missing proposal facts or transport receipts, expired reviews and altered archived source bytes. Historical archive hashes do not prove current live model quality. |
| tests/test_guided_callback_cancel_reset.py | Source read; synthetic SQLite/callback tests cover cancellation history boundary, old-button replay, forged results, missing delivery receipts, foreign owner and fresh-context preservation. They do not establish real Telegram delivery or model quality. |
| tests/test_guided_contracts.py | Source read; strict pure contract tests reject model save/confirm authority, malformed callback tokens, invalid provenance, stale review witnesses and cross-owner state while retaining historical v1 payload decoding. This is contract coverage, not integration acceptance. |
| tests/test_guided_controller.py | Source read; pure reducer tests keep model candidates outside write authority, require offered owner-bound choices and delivered review, preserve topic provenance, reject stale/expired/reserved/overflow states and consume confirmation once. No live transport. |
| tests/test_guided_conversation.py | Source read; fake Telegram/model and temporary SQLite cases cover guided choice routing, expiry, provenance, pending writes, fallback and purchase guards. No live transport/model proof. |
| tests/test_guided_events.py | Source read; synthetic event/replay identity, callback acknowledgment, delivery receipt, owner-binding corruption and callback-to-legacy refusal tests; no live Telegram receipt proof |
| tests/test_guided_final_fixes.py | Source read; synthetic expiry/reset, callback-history integrity, slow-HTTP expiry, oversized-choice refusal and rollback cases. Real model/Telegram gates remain open. |
| tests/test_guided_migration.py | Source read; synthetic v9-to-v10 preservation, failed-migration rollback and newer-schema refusal tests; no historical production database exercised |
| tests/test_guided_native_integration.py | Source read; fake HTTP test checks shared fixed skills, tool proposal, bounded request payload and runner settings; no real model inference |
| tests/test_guided_ollama.py | Source read; mocked HTTP cases constrain candidate-only model authority, payload/history bounds, malformed and oversize refusals, timeouts and untrusted context. No real inference. |
| tests/test_guided_provenance.py | Source read; owner/source, delivered-review digest, retained-state corruption, callback secrecy, mode revocation and v1-to-v2 provenance cases in temporary SQLite. |
| tests/test_guided_replies.py | Source read; deterministic full review, unsaved/candidate wording, UTF-16 length refusal and quantity-summary assertions; no live Telegram rendering |
| tests/test_guided_runtime.py | Source read; synthetic opt-in/disable, owner-before-dispatch and ack-before-model tests with fake transport/checkout; no live worker or Telegram acceptance |
| tests/test_guided_storage.py | Source read; temporary SQLite cases cover delivered-review witness, callback replay, expiry, revision/reservation revalidation, transaction rollback, unknown delivery and legacy reducer isolation. No private data or live Telegram exercised. |
| tests/test_guided_telegram_io.py | Source read; PTB models with fake Bot cover callback validation/ack, uncertain send receipts, restart/replay, owner checks and nonaccredited oversized replies. No live Telegram delivery. |
| tests/test_migration_distribution.py | Source read; first-pass review, independent QA pending |
| tests/test_natural_dialogue_probe.py | Source read; subprocess probe tests use injected HTTP for real provider codecs, assert replay/TTL/authority and PASS/FAIL/PENDING exits; no real model or Telegram acceptance |
| tests/test_natural_dialogue_runtime.py | Source read; temporary SQLite, mocked Ollama HTTP and fake Bot tests cover contextual add/increment guards, greeting privacy, pending-state preservation, prepared-v1 recovery, commit/restart replay and foreign owner refusal. No real model or Telegram run. |
| tests/test_natural_presentation.py | Source read; typed v2 phrase/schema consistency, grounded pending/result wording, historical v1 decoding and context budget cases with mocked writer. No model-quality proof. |
| tests/test_offers.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/test_ollama_interpreter.py | Source read; mocked loopback HTTP tests constrain source-verified dialogue schema, bounded/redacted context, local-only transport, failure fallback and no model purchase authority. No real semantic quality evidence. |
| tests/test_ollama_replies.py | Source read; mocked local HTTP tests constrain public snapshot schema, no tool calls, strict provider/phrase validation, bounded context/timeouts and no private fallback or proxy leakage. No real model quality. |
| tests/test_pending_additions.py | Source read; pending add remains outside saved list until quantity, duplicate permission rebinding, nonrenewing queries, v8 migration and prepared v1 recovery use synthetic SQLite. |
| tests/test_presentation_replies.py | Source read; deterministic duplicate, quantity/replacement, stale/reserved, historical product and large-list rendering cases. Source rows remain application facts. |
| tests/test_presentation_storage.py | Source read; synthetic v6-to-v10 migration, prepared/finalized presentation replay, owner/source corruption, notice matching and atomic rollback cases. No private database exercised. |
| tests/test_presentation_validation.py | Source read; rejects invented numbers, products, URLs, success claims, missing/reordered references and budget overflow; validates trusted command suffix and literal hostile product data. |
| tests/test_private_acl.py | Source read and focused/full suite executed; Windows owner and exact ACL assertions reviewed, independent QA pending |
| tests/test_product_memory.py | Delegated full-source review in TAK-10 audit-stores rev 43d40f09, PR #16 at b4b8e279; baseline path unchanged locally. Historical fixture/test scope; QA and exact-SHA CI pending. |
| tests/test_product_queries.py | Source read; synthetic repository tests separate dated observations from current offers, reject generic/untrusted backlog requests, and assert replay plus transaction rollback; no refreshed public price evidence |
| tests/test_recovery.py | Source read; fake-store reconciliation requires external evidence, preserves uncertain rows, avoids blind resubmit, limits outbox replay and protects split allocations. No real store transaction. |
| tests/test_reply_conversation.py | Source read; fake writer/interpreter cases preserve deterministic command routes, prepared replay, snapshot facts, TTL and complete fallback on invalid/overbudget drafts. No real model quality. |
| tests/test_reply_probe.py | Source read; PowerShell probe subprocess uses offline fixtures, private-read sentinel and PASS/FAIL/PENDING cleanup assertions; no current Ollama or Telegram exercise |
| tests/test_reply_runtime.py | Source read; fake-model/Telegram runtime tests cover commands-only fallback, owner rejection and no checkout/order access; no live transport or model acceptance |
| tests/test_runtime.py | Source read; synthetic settings, process lock, fake transport and temporary SQLite tests cover owner binding, model enable/disable preservation, command fallback, restart/recovery order, pending outbox, secret redaction and Windows ACL fail-closed behavior. A Windows ACL test touches only its temporary file. |
| tests/test_storage.py | Source read; synthetic SQLite tests cover atomic inbox/outbox, immutable order snapshots, duplicate delivery, strict quantity/identity and unknown quantity refusal. No private database or purchase. |
| tests/test_telegram_io.py | Source read; PTB models with mocked Bot/HTTP cover owner-only direct messages, atomic polling offset, durable outbox retries, plain text, UTF-16 splitting and rejected relayed commands. No live Telegram acceptance. |
| third_party/shopping-list-skill/LICENSE | Source read; first-pass review, independent QA pending |
| third_party/shopping-list-skill/NOTICE.md | Source read; first-pass review, independent QA pending |
## Added candidate paths

The workflow, installed-wheel smoke script and archive attributes were read and tested as described above. Delivery documents are authored evidence. The concurrent `staffing.md` addition is preserved; its scope and approval remain owned by TAK-2. These additions are outside the fixed 278-path baseline ledger.

## TAK-9 continuation, 2026-10-12

### P0-06 — HIGH: doctor changed the database it was diagnosing

`cli.doctor` called `Repository.migrate()`. A synthetic schema-9 database with a preserved product row, fake Telegram Bot and fake Playwright reproduced the contract breach: `doctor` returned `SQLite: OK` and advanced `PRAGMA user_version` to 10. The RED test is `tests/test_doctor_read_only.py::test_doctor_does_not_upgrade_existing_schema`. The candidate now opens the existing database in SQLite read-only mode, checks its version and reports `SQLite: blocked (schema update required)` without migrating or reseeding it. Focused GREEN and lint evidence is in [verification.md](verification.md). The test is a synthetic diagnostic; no private database was opened.

### P0-07 — HIGH: actual CI ACL failure remains open

[Run 38268644004, job 114877125611](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38268644004/job/114877125611) completed with 29 failed and 1629 passed tests. The failed nodes depend on Windows private-tree ACL verification; Ruff and diff checks passed, and wheel stages were skipped. A local synthetic scratch run passed, so the mismatch required runner evidence. Do not weaken ACL expectations or call CI green.

The first diagnostic candidate, `e64fca0`, reached [run 38272674378](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38272674378) but stopped before pytest: direct `scripts/ci_acl_probe.py` execution lacked the repository import path on that host. The workflow now invokes the probe as a module; this is an entry-point correction, not an ACL repair.

[Run 38273126818 at `24611ca`](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38273126818) completed with 29 failed, 1630 passed in 341.32s. Its sanitized scratch probe established the mismatch: `owner_matches=False` while the single allow rule had the correct user SID, full rights, inheritance and propagation. Both batch and single-path ACL verification failed for that reason. The candidate now sets the file/directory owner to the authenticated user SID before committing the DACL, then retains exact owner and rule readback. [Run 38275905585 at `efc4f03`](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38275905585) proved the repair on the CI runner: sanitized batch and single-path owner/rule readback passed, and 1660 tests passed. Its one failure was a new doctor test fixture that created a database after securing the private tree, so read-only doctor correctly refused its inherited CI ACL. The synthetic fixture now explicitly secures that file before the no-write assertion; focused ACL/doctor tests pass locally. Corrected-candidate CI at `43e58c1` passed 1661 offline tests, ACL diagnostic, Ruff, whitespace and installed-wheel smoke; see [verification.md](verification.md).

The subsequent documentation-head [CI run 38282736456, job 114923683151](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38282736456/job/114923683151) at `6aebec19e55c7da50105a02cd9ccab413cc7f8b3` also completed successfully: 1661 offline tests in 561.40s, Ruff, whitespace, synthetic ACL diagnostic and installed-wheel smoke. This closes the CI repair verification at that SHA; it does not close the manual audit or release gates.

### P0-08 — HIGH: doctor entered a filesystem ACL writer (repair verified in CI)

Static trace after the initial schema repair: `cli.py:101` called `load_settings(root)`; `config.py:244` invoked `_private_tree(root / "private")`, applying ACLs to every path. Synthetic RED tests caught that write path and a foreign ACL grant that doctor silently repaired before diagnosis. The candidate now calls `load_settings(read_only=True)`, which preflights links and reads effective owner-only ACLs without applying them. A foreign grant blocks the diagnostic and remains unchanged. Focused tests and full candidate CI passed; independent review remains pending.

### Seven-package native-agent reconciliation against the merged baseline

The October 8 implementation plan, spec, merged commit history and named test files show these packages are present. This table records the earlier checkpoint; the final evidence reconciliation follows the path ledger below. Existing interfaces are retained; migration 009 is already merged and remains untouched.

| Package | Merged implementation / origin | Relevant tests | Remaining evidence |
| --- | --- | --- | --- |
| 1. Contracts and fixed skills | `shopping_agent/contracts.py`, `skills.py`, four packaged skills and MIT notice; `edf1d2b` | `test_agent_contracts.py`, `test_agent_skills.py` | Independent detailed source review pending. |
| 2. Pure proposals and replies | `shopping_agent/proposals.py`, `replies.py`; `4bbe76e` | `test_agent_proposals.py`, `test_agent_replies.py` | Real semantic selection and duplicate interpretation still fail historically. |
| 3. Atomic persistence and provenance | `shopping_agent/storage.py`, existing `migrations/009.sql`, repository mixin; `5cc7107` plus provenance fixes | `test_agent_storage.py`, `test_agent_recovery.py`, `test_command_query_provenance.py` | Full audit of stale/foreign/expired and recovery paths pending; no migration reuse. |
| 4. Seven controlled tools | `shopping_agent/tools.py`; `75dd652` | `test_agent_tools.py` | Real E4B can choose a valid but wrong tool; historical quality gate remains. |
| 5. Bounded local E4B loop | `shopping_agent/ollama.py`; `6f7b681` | `test_agent_ollama.py` | No new real-model run is authorized in this audit. |
| 6. Opt-in routing and rollback | `shopping_agent/conversation.py`, `runtime.py`, `cli.py`, `dialogue_storage.py`; `55d8997` and later fixes | `test_agent_conversation.py`, `test_agent_runtime.py`, `test_agent_route_notices.py` | The diagnosed ACL owner mismatch is repaired and actual CI passed at `43e58c1`; independent review remains pending. |
| 7. Offline and real acceptance | `scripts/probe_skills_agent.py`, end-to-end/probe tests and archived JSONL; `2df0d08` | `test_agent_end_to_end.py`, `test_agent_probe.py` | Two frozen real runs each passed 50/53 steps; saved-list query and internal-duplicate completion failed. Guided v5 quality also remains failing. No Telegram acceptance. |

Latest CI follow-up: [run 38298055578](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38298055578/job/114974162243) at `b87a4ef69171add0eaab21ea7a0930ed029d3b95` failed the whitespace step before tests. Both added documentation files ended with a carriage-return-only line, which Git reported as trailing whitespace. The local correction removes those lines; full offline CI and independent audit review remain outstanding for the resulting candidate.

2026-10-13 continuation: Puente integrated Alpha source `361a0ef732493483ffdc406eec3e2ca0bf4a7fac` into PR #11 head `1f65868fba456c05db71cb67ccdc09e91d20d05d`. Managed GitHub PR/check reads confirm [Windows job 115009527242](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38308893952/job/115009527242) completed successfully at that remote SHA; Puente records 1661 offline tests passed and the Ruff, whitespace, ACL and installed-wheel stages successful. This repairs the prior whitespace failure at the integrated SHA. Nine more owned historical documents were fully reviewed in this local continuation, as marked above. Remaining Pending rows and source-review gaps are not closed; no independent QA, real-model quality or live Telegram acceptance is claimed.

2026-10-13 later continuation: Puente integrated local audit source `b4506cff0a7740f4013d346498000952a9208bbc` into PR #11 head `c90e852714a05d0c58b59f724a040ef08932786e`. Managed GitHub PR/check reads confirm [Windows job 115159738937](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38356256108/job/115159738937) completed successfully at that exact remote SHA. Six additional owned historical source documents were read and classified above. This new local ledger update is not in that PR head; its CI status is therefore pending. Manual coverage, independent QA, real-model quality and Telegram acceptance remain open.

Batch A checkpoint, 2026-10-13: three historical dialogue specifications above were fully read and classified. Their application-owned authorization and stale-state controls support the seven-package contract, while the archived guided free-dialogue failures keep real-model quality open. This is a local checkpoint under the consolidated A/B coordination; it is not an integration request or a PASS claim.

Batch B checkpoint, 2026-10-13: five test-helper sources above were fully read. Their boundaries explain which assertions use real temporary SQLite and which use fake model, Telegram and store responses. No product behavior was changed or newly tested in this checkpoint. The A/B inventories and all remaining source gaps stay open.

Batch A/B checkpoint, 2026-10-13: one historical presentation implementation plan and three owned test files were fully read and classified above. The plan's no-replay and grounded-output requirements are represented by test coverage, while guided callback cancellation tests specifically protect a previously observed replay/history defect. No new product tests or live probes ran in this documentation-only checkpoint; remaining inventory, QA and release gates stay open.

Batch B continuation, 2026-10-13: three further owned test sources were fully read and classified above. Their assertions rely on synthetic migration data and fake runtime boundaries; they establish neither private database compatibility nor live Telegram/model behavior. No product tests or probes were run for this documentation checkpoint. The A/B inventories and final candidate CI remain open.

Batch A continuation, 2026-10-13: `docs/superpowers/progress.md` was read in full. Its dated results include earlier failed and passing real-model probes, historical public store observations and repeated Telegram-not-accepted statements. Those historical model results do not resolve the separate native/guided quality gap recorded elsewhere in this audit. The opening 2026-10-12 CI-pending note is stale against the later exact-SHA CI records; final candidate CI remains a separate gate. No historical evidence was changed.

Batch B continuation, 2026-10-13: four further owned test sources were fully read and classified above. Native/guided probe tests can exercise production codecs with injected HTTP while still lacking real model inference; product-query tests prove persistence rules with synthetic SQLite, not current public prices. No product tests or live probes ran for this audit entry.

Batch A continuation, 2026-10-13: the natural-dialogue implementation plan was fully read. It demands that saved rows remain unchanged until quantity/selection/confirmation, that changed base quantities invalidate an old yes, and that prepared v1 presentations recover without reapplying a mutation. These are historical requirements to reconcile against current code/tests, not a fresh authorization to execute the plan's old worktree or agent instructions.

Batch B continuation, 2026-10-13: guided event/runtime test sources were fully read. They exercise durable callback identity, owner validation and acknowledgment order in synthetic repositories with fake transport, including disabled guided routing; they cannot establish actual Telegram delivery acknowledgments or private worker behavior.

Batch B continuation, 2026-10-13: five contextual-dialogue test sources were fully read. They cover pending additions, selected increments, maximum SQLite quantities, source-grounded request parsing and migration/state storage with isolated databases. Tests assert that old confirmations fail on changed or reserved rows and that replay does not repeat a write. Their fake or mocked interpreter paths do not close the historical real-model quality gate.

Batch A continuation, 2026-10-13: the contextual Gemma plan was fully read. Its security contract keeps the model's product mention separate from application authority, requires owner/source and current-revision checks, and forbids replay from renewing a pending decision. The plan predates later schema 8–10 work; audit conclusions use the merged implementation and tests rather than its proposed migration number or old execution workflow.

Batch B continuation, 2026-10-13: test_guided_conversation.py, test_guided_ollama.py and test_guided_storage.py were fully read. They verify that guided model outputs remain candidate data and that only application-owned, current, delivered choices may mutate the synthetic list. Storage failpoints check rollback of state, outbox and event consumption together. All Telegram/model boundaries in these tests are fake or mocked. These reads do not establish live quality or delivery. No product tests or probes were run for this docs-only checkpoint.

Batch B continuation, 2026-10-13: six further owned test sources were fully read and classified above. The guided provenance/final-fix/transport tests exercise retained-state validation, actual delivery receipts and callback replay with synthetic SQLite and fake Telegram/network boundaries; historical presentation tests require grounded facts, complete references and bounded output without claiming uncommitted changes succeeded. Their tests do not supply live Telegram or real-model quality evidence. No product tests or probes were run for this documentation checkpoint.

Batch B continuation, 2026-10-13: three more owned dialogue/presentation test sources were fully read. They verify the legacy confirmation vocabulary and expiry, replacement source and duplicate revision checks, and prepared-presentation transactional replay with temporary SQLite. Historical migration fixtures and fake interpreters cannot prove compatibility with private data or real language understanding. No product tests or probes were run for this docs-only continuation.

Batch B continuation, 2026-10-13: four offline integration, recovery, storage and reply-conversation test files were fully read. Their fake Bot/Store paths demonstrate replay and uncertain-result safeguards without exercising any real store purchase. Prepared-presentation tests use a fake writer and temporary SQLite; they establish fallback and transaction boundaries but not real-model wording. No product tests, live probes or private database access were performed for this audit-only update.

Batch B continuation, 2026-10-13: the offline Telegram transport and Ollama reply-writer tests were fully read. They use real PTB object parsing and provider JSON codecs behind fake network transports, validating offset/outbox durability and strict grounded reply shape without touching a live bot or local model. Their boundary evidence does not close the separate Telegram pilot or semantic quality gates.

Batch B continuation, 2026-10-13: the legacy contextual conversation and Ollama interpreter tests were fully read. Model outputs remain proposals checked against source text and current offered choices; explicit commands and closed answers bypass inference. Mocked HTTP and fake interpreter flows protect authorization and persistence boundaries but do not resolve historical language-quality failures.

Batch B continuation, 2026-10-13: checkout, legacy conversation and dialogue end-to-end test files were fully read and classified above. Their temp-database, fake-store, fake-interpreter and fake-Telegram cases provide offline authorization and replay evidence, while live purchase, Telegram delivery and real-model quality remain unverified. No product tests or probes ran for this documentation-only checkpoint.

Batch B continuation, 2026-10-13: guided acceptance/controller and natural dialogue runtime test sources were fully read. The verifier tests distinguish immutable historical traces from current execution evidence and reject falsified model or delivery records. The pure controller and synthetic runtime cases guard application-owned authorization and restart behavior, but they do not close live-model quality or Telegram gates. No product tests or probes ran for this documentation-only checkpoint.

Batch B continuation, 2026-10-13: the general runtime test source was fully read. It exercises settings and worker-lock safety, owner checks before recovery, provider failure fallback and durable pending work using isolated fixtures. The Windows ACL integration case is confined to a temporary file; this audit did not execute it or access private configuration. No product tests or live probes ran for this documentation-only checkpoint.

Batch A continuation, 2026-10-13: `docs/setup.md` was fully read. Its Windows commands and dated e2b probe results are operational history, while the guide explicitly leaves private bot activation and Telegram acceptance gated. The current E4B release candidate and live-quality evidence require separate review; no setup command, service action, model download or private-data operation was run for this audit.

Batch A/B continuation, 2026-10-13: both remaining owned probe scripts were fully read and classified. A path-set check against baseline `b9a29049160cc53737d1cb64a8138385aa2fedd2` found exactly 278 unique ledger paths for 278 tracked baseline paths, with none missing or extra. After this update, 217 rows say `Source read`, 51 remain `Pending`, nine retain explicit full-source-review gaps in delegated store scope, and one guided-evidence handoff says initial inspection/full audit pending. These counts reconcile inventory labels only; they do not close the 51 pending paths, independent QA, native semantic quality or Telegram acceptance. No probe or product test was run in this docs-only checkpoint.

Batch A/B continuation, 2026-10-13: the two Windows PowerShell probe sources were fully read. `Probe-NaturalDialogue.ps1` gates synthetic conversation safety and e2b model-backed add/increment/list wording separately; `Probe-Replies.ps1` gates application-grounded presentation, replay and transaction boundaries, with offline rejection distinct from draft quality. Both are opt-in and use temporary invented data. Neither script was executed here. The baseline ledger remains 278 unique rows, now 219 `Source read` and 49 `Pending`; nine delegated store full-source-review gaps and one guided-evidence initial inspection remain. No live-model or Telegram evidence was produced.

Batch A continuation, 2026-10-13: the historical Gemma reply report was fully read, including failed raw drafts, the conditioned-schema repair, both PASS samples, metrics and final text. Its two accepted local e2b samples use fixed application-owned facts/options and fake interpretation on invented databases. This historical record does not establish current E4B quality or Telegram delivery. The baseline ledger remains 278 unique rows, now 220 `Source read` and 48 `Pending`; no probe or product test ran for this docs-only update.

Batch A continuation, 2026-10-13: the guided Telegram implementation plan was fully read. The three later frozen matrices were parsed across all 28 cases and 124 steps each, and their complete revision diffs compared. V3 and v5 cases and model parameters match; v4 changed Spanish text into mojibake while claiming unchanged expectations. The existing v4 evidence already treats that evaluation as invalid. These matrix files are frozen test inputs, not real-model results. The baseline ledger remains 278 unique rows, now 224 `Source read` and 44 `Pending`; no probe or product test ran for this docs-only review.

## Consolidated 278-path disposition, 2026-10-13

The fixed product baseline `b9a29049160cc53737d1cb64a8138385aa2fedd2` contains 278 tracked paths. The ledger above has exactly 278 unique rows with zero missing or extra baseline paths. All 263 core/owned paths have a direct source or complete structured-evidence review. Fifteen store fixtures/tests were read in full by the Store Integration Engineer in [TAK-10 audit-stores](/TAK/issues/TAK-10#document-audit-stores), revision `43d40f09-2b51-4edd-903a-e4464eb6a99b`; their baseline paths are unchanged locally. The delivered report covers all 30 store-scope paths and is published in [draft PR #16](https://github.com/Adolfoderueda/project_shop_assistant/pull/16), head `b4b8e279bc6b2acc67a237cca1e2c984dabb1370`, report blob `d9d640726f6d71718dfc7ccbe81d12684a3ba4dc`. This is attributed delegated review, not Alpha's reread or independent QA. The [final manifest](manifest.md) records every baseline path and Git blob.

The 36 previously pending JSONL files were streamed line by line: **7,349 JSON records, 118,909,971 checkout bytes, zero parse errors**. Exact per-file checkout SHA-256, record counts, statuses and guided conversation totals are in [evidence-manifest.json](evidence-manifest.json). CRLF checkout bytes can differ from LF Git blobs; recorded guided matrix hashes match the LF-normalized matrix, not raw Windows checkout bytes. The three other pending owned artifacts were fully read: the 639-line historical RED log, the seven-case/18-call preregistration JSON and the guided handoff. Historical traces are not fresh execution.

The archived native offline files each report 76/76 synthetic steps, with real quality `NOT_TESTED`. The two final-review real files each report 73/76 step passes but `FAIL` quality. The native ablation has 5/18 semantic successes, 8/18 strictly valid native calls and 10/18 safe fallbacks. Guided v5's complete recorded conversations score 42/102 bounded, 6/39 security and 0/24 general in real mode; offline v5 scores 102/102, 30/39 and 24/24 respectively. The v5 JSONL includes 381 unexecuted steps following failures. V4 contains damaged Spanish text, so its historical real comparison is invalid. These observations sustain **P0-04 HIGH**, routed to [TAK-4](/TAK/issues/TAK-4) as a product quality gate. No fresh model or Telegram run occurred.

### Seven-package disposition

| October 8 package | Baseline finding | Disposition / owner |
| --- | --- | --- |
| 1. Contracts and packaged skills | Fixed tool contracts and four packaged skills exist; the installed-wheel smoke now checks packaged resources. | Implemented; no P0 source gap. Izpi reviews integrated SHA. |
| 2. Pure proposals and replies | Application-owned proposal/reply rules are present; native semantic duplicate/query failures remain in archived real evidence. | Implemented, quality gate P0-04 open under TAK-4. |
| 3. Atomic storage and provenance | Schema 009, transaction and stale/foreign/expired/duplicate safeguards are present; historical RED provenance log is superseded by repaired tests and CI. | Implemented; final integrated CI and Izpi review pending. |
| 4. Seven controlled tools | Seven strict tools and whole-batch validation are present; a valid but wrong real tool choice remains possible. | Implemented, P0-04 remains open under TAK-4. |
| 5. Bounded E4B loop | Local bounded loop and fallback handling are present; fallback is not semantic success. | Implemented, no current real-model acceptance. |
| 6. Opt-in integration | Runtime routing and rollback are present; doctor/ACL defects P0-06 to P0-08 were repaired and previously CI-tested. | Implemented; preserve offline default and no live activation. |
| 7. Acceptance probes | Offline probes and historical real traces are archived. Full JSONL audit identifies executed versus skipped steps. | Synthetic gate previously green; real-model and Telegram gates pending. |

P0-01, P0-02, P0-03, P0-06, P0-07 and P0-08 have recorded reproductions, repairs and prior exact-SHA CI in [verification.md](verification.md); their final integrated candidate still requires CI and independent review. P0-05 is the open governance gate until Puente [TAK-23](/TAK/issues/TAK-23) publishes this dossier and verifies the resulting PR #11 SHA, then Izpi [TAK-11](/TAK/issues/TAK-11) reviews that SHA. The store audit's high pack-identity repair has RED and 137 focused PASS, but PR #16 CI/review is separate and pending. Medium P3 handoffs are partial search coverage, empty-result timeout, and the historical-only `consultar_ficha` boundary. No current public price or shipping total was established.

This closes the **baseline path-review inventory**, not TAK-9 release acceptance. Puente owns one remote writer and final exact-SHA CI; Izpi owns independent QA. Takeshi retains merge, activation and final acceptance.
