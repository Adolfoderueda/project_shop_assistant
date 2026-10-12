# Baseline audit â€” execution and first-pass findings; incomplete

Observed 2026-10-12. Owner/author: Mushu. Independent reviewer: pending staffing on [TAK-2](/TAK/issues/TAK-2). Work: [GitHub #5](https://github.com/Adolfoderueda/project_shop_assistant/issues/5) / [TAK-3](/TAK/issues/TAK-3). Tracking: #4. Draft [PR #11](https://github.com/Adolfoderueda/project_shop_assistant/pull/11).

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

### P0-01 â€” HIGH: installed distribution cannot import storage (repair submitted)

`pyproject.toml` omits `product_memory` from explicit flat modules. `storage.py` and `dialogue_requests.py` depend on it. Build with `python -m pip wheel . --no-deps --no-build-isolation --no-index`; install into an empty target; outside the repository set `PYTHONPATH` to that target and run `python -P -c "import storage"`. Baseline raises `ModuleNotFoundError: No module named 'product_memory'`. Editable/source tests mask the defect.

Repair in `1c63ec1`: include that module and run `scripts/check_installed_wheel.py` against the installed target. RED then GREEN observed. No schema or product behavior changed. Independent review and final full candidate check remain pending. Tracked in #5 / PR #11.

### P0-02 â€” MEDIUM: frozen archive checks depend on local Git line endings (repair submitted)

Failures: `tests/test_guided_acceptance.py::test_archive_integrity_distinguishes_recorded_probe_from_current_verifier` and `::test_v3_exact_runtime_is_independently_archivable_without_hash_exemption`.

The four v2/v3 offline/real JSONL Git blobs contain LF, while immutable execution hashes describe CRLF. `verify_integrity` rejects the clean LF checkout as changed raw evidence. For all four, reconstructing CRLF matches the pre-existing expected SHA-256. The new local `.gitattributes` pins `text eol=crlf` for exactly those files; Git blobs, recorded hashes, matrices and expectations are unchanged. After materializing the declared checkout bytes, both tests pass. Existing objects for the pinned archive commits must be available, so CI fetches full Git history. Tracked in #5 / PR #11.

### P0-03 â€” MEDIUM: guided probe assumes Takeshi's Windows temporary path (repair submitted)

`scripts/probe_guided_questions.py` hardcoded `C:/Users/Takeshi/AppData/Local/Temp/opencode`. A host with another user cannot run synthetic acceptance reliably; it also ignores the run's temporary-directory boundary. An audit hook rejected actual `tempfile.mkdtemp` outside the platform temp root. Replacing the constant with `Path(tempfile.gettempdir())` passed the same synthetic one-each probe and cleanup check. Historical artifacts were not regenerated. The legacy PowerShell probes additionally require an existing `%LOCALAPPDATA%/Temp/opencode`; CI explicitly prepares that synthetic directory. Tracked in #5 / PR #11.

### P0-04 â€” HIGH release gate: native quality remains below documented acceptance

Historical native and guided evidence records semantic failures, not merely unavailable services. Native-agent execution status reports 50/53 steps on each of two runs, with saved-list query and internal-duplicate failures. Guided v5 reports 42/102 bounded, 6/39 security and 0/24 free conversations; many later steps were not reached. The subsequent callback-boundary fix has offline evidence but no new native acceptance. These are historical observations, not rerun results. Retain the no-activation gate and resolve quality under P1 with a reviewed interface/design before changing the native contract. No speculative prompt or model changes were made here.

### P0-05 â€” governance: CI and independent review still pending

Baseline has no workflows. Proposed Windows workflow now runs full offline tests, Ruff, diff and installed-wheel smoke without production credentials or model services. Setup follows [GitHub's Python workflow guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python). A completed actual run is required before calling CI established. Previous access checks reported unprotected default branch and 403 for protection/rulesets on this private account tier. No subscription/visibility change; manual independent-review and Takeshi merge gates remain.

## First-pass architecture observations

- Agent tools have no purchase/confirm tool, validate an entire native batch, permit one final mutator, and bind operations to a durable inbox snapshot. Agent storage atomically revalidates rows/reservations and commits list changes with the reply. Guided provenance/reducer/storage still needs the remaining detailed review.
- Telegram accepts authorized private sender/chat events, rejects forwarded/quoted provenance, stores inbox offsets durably and records delivered notices. Its documented at-least-once notices can duplicate after ambiguous send responses; do not promise exactly-once external delivery.
- SQL migrations 1â€“10 are versioned resources. They preserve immutable order snapshots and quarantine old checkout permissions; none creates named lists or reminders. Do not downgrade a schema-10 database to old code.
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
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-red-corrected.txt | Pending |
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
| docs/setup.md | Relevant sections inspected; full source review pending |
| docs/store-capabilities.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/continuacion-gemma-2026-10-01.md | Source read; historical quality and ACL work, private Telegram gate remains |
| docs/superpowers/continuacion-gemma-lista-2026-09-30.md | Source read; historical list/card implementation and quality limits, independent QA pending |
| docs/superpowers/continuacion-telegram-2026-09-28.md | Source read; historical user-reported Telegram activity, no current pilot or restart evidence |
| docs/superpowers/evidence/2026-10-08-skills-agent/README.md | Source read; historical original real 31/53 in both frozen passes, fix-round real 50/53 with three failures; no new real acceptance |
| docs/superpowers/evidence/2026-10-08-skills-agent/execution-status.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md | Source read; confirms 50/53 real steps in each frozen run and three semantic failures; independent QA pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix-round-1.md | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-offline.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-control.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-recipe.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-control.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-full-real.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-recipe.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-contract.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-control.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-contract.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-control.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-full-real.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-scope.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/fix1-schema-only-real.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/offline.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/real-pass-1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/schema-diagnostic.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/skill_micro_probe.py | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/verification.txt | Pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/.gitattributes | Pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/preregistration.json | Pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/results.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/trials.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v3-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v4-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v5-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v2.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v3.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/execution-status.md | Source read; first-pass review, independent QA pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v3.md | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v4.md | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v5.md | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/handoff.md | Initial inspection; full audit pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v4.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v5.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1-source.txt | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v3.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v4.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v5.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v3.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v4.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v5.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/results.md | Pending |
| docs/superpowers/gemma4-12b-local-2026-10-10.md | Pending |
| docs/superpowers/natural-dialogue-real-2026-10-08-run1.jsonl | Pending |
| docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl | Pending |
| docs/superpowers/natural-dialogue-real-2026-10-08-run3.jsonl | Pending |
| docs/superpowers/plans/2026-09-27-asistente-compras.md | Pending |
| docs/superpowers/plans/2026-09-29-gemma4-local-telegram.md | Pending |
| docs/superpowers/plans/2026-09-29-lista-fichas-gemma.md | Pending |
| docs/superpowers/plans/2026-10-01-conversacion-contextual-gemma.md | Pending |
| docs/superpowers/plans/2026-10-08-agente-skills-herramientas.md | Pending |
| docs/superpowers/plans/2026-10-08-dialogo-natural-altas-incrementos.md | Pending |
| docs/superpowers/plans/2026-10-08-respuestas-naturales-gemma.md | Pending |
| docs/superpowers/plans/2026-10-09-preguntas-guiadas-telegram.md | Pending |
| docs/superpowers/progress.md | Pending |
| docs/superpowers/prueba-dialogo-contextual-2026-10-01.md | Pending |
| docs/superpowers/prueba-dialogo-natural-2026-10-08-run3.md | Pending |
| docs/superpowers/prueba-dialogo-natural-2026-10-08.md | Pending |
| docs/superpowers/prueba-gemma-2026-10-01.md | Pending |
| docs/superpowers/prueba-respuestas-gemma-2026-10-08.md | Pending |
| docs/superpowers/specs/2026-09-27-asistente-compras-design.md | Pending |
| docs/superpowers/specs/2026-09-29-gemma4-local-telegram-design.md | Pending |
| docs/superpowers/specs/2026-09-29-lista-fichas-gemma-design.md | Pending |
| docs/superpowers/specs/2026-10-01-conversacion-contextual-gemma-design.md | Pending |
| docs/superpowers/specs/2026-10-08-agente-skills-herramientas-design.md | Source read; confirmation, tool and acceptance contracts reconciled above; independent QA pending |
| docs/superpowers/specs/2026-10-08-dialogo-natural-altas-incrementos-design.md | Pending |
| docs/superpowers/specs/2026-10-08-respuestas-naturales-gemma-design.md | Pending |
| docs/superpowers/specs/2026-10-09-preguntas-guiadas-telegram-design.md | Pending |
| docs/superpowers/task-8-report.md | Pending |
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
| requirements.lock | Pending |
| restrictions.py | Source read; first-pass review, independent QA pending |
| runtime.py | Source read; first-pass review, independent QA pending |
| scripts/Install-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Probe-Dialogue.ps1 | Pending |
| scripts/Probe-NaturalDialogue.ps1 | Pending |
| scripts/Probe-Replies.ps1 | Pending |
| scripts/Start-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Stop-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/Uninstall-ShopAssistant.ps1 | Source read; first-pass review, independent QA pending |
| scripts/diagnose_guided_native_v2.py | Pending |
| scripts/probe_guided_questions.py | Relevant sections inspected; full source review pending |
| scripts/probe_skills_agent.py | Relevant sections inspected; full source review pending |
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
| tests/agent_support.py | Full suite executed; source review pending |
| tests/dialogue_support.py | Full suite executed; source review pending |
| tests/factories.py | Full suite executed; source review pending |
| tests/fakes.py | Full suite executed; source review pending |
| tests/fixtures/stores/amascotados.html | Pending |
| tests/fixtures/stores/charro.html | Pending |
| tests/fixtures/stores/mercadona-search.html | Pending |
| tests/fixtures/stores/mercadona.html | Pending |
| tests/fixtures/stores/nappy-out.html | Pending |
| tests/fixtures/stores/nappy.html | Pending |
| tests/guided_helpers.py | Full suite executed; source review pending |
| tests/stores/test_amascotados.py | Full suite executed; source review pending |
| tests/stores/test_browser.py | Relevant sections inspected; full source review pending |
| tests/stores/test_charro.py | Full suite executed; source review pending |
| tests/stores/test_contract.py | Full suite executed; source review pending |
| tests/stores/test_mercadona.py | Full suite executed; source review pending |
| tests/stores/test_nappy.py | Full suite executed; source review pending |
| tests/stores/test_public_adapters.py | Full suite executed; source review pending |
| tests/test_agent_contracts.py | Relevant sections inspected; full source review pending |
| tests/test_agent_conversation.py | Full suite executed; source review pending |
| tests/test_agent_end_to_end.py | Full suite executed; source review pending |
| tests/test_agent_ollama.py | Full suite executed; source review pending |
| tests/test_agent_probe.py | Full suite executed; source review pending |
| tests/test_agent_proposals.py | Full suite executed; source review pending |
| tests/test_agent_recovery.py | Full suite executed; source review pending |
| tests/test_agent_replies.py | Full suite executed; source review pending |
| tests/test_agent_route_notices.py | Full suite executed; source review pending |
| tests/test_agent_runtime.py | Full suite executed; source review pending |
| tests/test_agent_skills.py | Full suite executed; source review pending |
| tests/test_agent_storage.py | Full suite executed; source review pending |
| tests/test_agent_tools.py | Full suite executed; source review pending |
| tests/test_checkout.py | Full suite executed; source review pending |
| tests/test_command_query_provenance.py | Full suite executed; source review pending |
| tests/test_conversation.py | Full suite executed; source review pending |
| tests/test_dialogue.py | Full suite executed; source review pending |
| tests/test_dialogue_conversation.py | Full suite executed; source review pending |
| tests/test_dialogue_end_to_end.py | Relevant sections inspected; full source review pending |
| tests/test_dialogue_increments.py | Full suite executed; source review pending |
| tests/test_dialogue_quantity_bounds.py | Full suite executed; source review pending |
| tests/test_dialogue_replacement.py | Full suite executed; source review pending |
| tests/test_dialogue_requests.py | Full suite executed; source review pending |
| tests/test_dialogue_storage.py | Full suite executed; source review pending |
| tests/test_end_to_end.py | Full suite executed; source review pending |
| tests/test_guided_acceptance.py | Relevant sections inspected; full source review pending |
| tests/test_guided_callback_cancel_reset.py | Full suite executed; source review pending |
| tests/test_guided_contracts.py | Full suite executed; source review pending |
| tests/test_guided_controller.py | Full suite executed; source review pending |
| tests/test_guided_conversation.py | Full suite executed; source review pending |
| tests/test_guided_events.py | Full suite executed; source review pending |
| tests/test_guided_final_fixes.py | Full suite executed; source review pending |
| tests/test_guided_migration.py | Full suite executed; source review pending |
| tests/test_guided_native_integration.py | Full suite executed; source review pending |
| tests/test_guided_ollama.py | Full suite executed; source review pending |
| tests/test_guided_provenance.py | Full suite executed; source review pending |
| tests/test_guided_replies.py | Full suite executed; source review pending |
| tests/test_guided_runtime.py | Full suite executed; source review pending |
| tests/test_guided_storage.py | Full suite executed; source review pending |
| tests/test_guided_telegram_io.py | Full suite executed; source review pending |
| tests/test_migration_distribution.py | Source read; first-pass review, independent QA pending |
| tests/test_natural_dialogue_probe.py | Full suite executed; source review pending |
| tests/test_natural_dialogue_runtime.py | Full suite executed; source review pending |
| tests/test_natural_presentation.py | Full suite executed; source review pending |
| tests/test_offers.py | Full suite executed; source review pending |
| tests/test_ollama_interpreter.py | Full suite executed; source review pending |
| tests/test_ollama_replies.py | Full suite executed; source review pending |
| tests/test_pending_additions.py | Full suite executed; source review pending |
| tests/test_presentation_replies.py | Full suite executed; source review pending |
| tests/test_presentation_storage.py | Full suite executed; source review pending |
| tests/test_presentation_validation.py | Full suite executed; source review pending |
| tests/test_private_acl.py | Source read and focused/full suite executed; Windows owner and exact ACL assertions reviewed, independent QA pending |
| tests/test_product_memory.py | Full suite executed; source review pending |
| tests/test_product_queries.py | Full suite executed; source review pending |
| tests/test_recovery.py | Full suite executed; source review pending |
| tests/test_reply_conversation.py | Full suite executed; source review pending |
| tests/test_reply_probe.py | Full suite executed; source review pending |
| tests/test_reply_runtime.py | Full suite executed; source review pending |
| tests/test_runtime.py | Full suite executed; source review pending |
| tests/test_storage.py | Full suite executed; source review pending |
| tests/test_telegram_io.py | Full suite executed; source review pending |
| third_party/shopping-list-skill/LICENSE | Source read; first-pass review, independent QA pending |
| third_party/shopping-list-skill/NOTICE.md | Source read; first-pass review, independent QA pending |
## Added candidate paths

The workflow, installed-wheel smoke script and archive attributes were read and tested as described above. Delivery documents are authored evidence. The concurrent `staffing.md` addition is preserved; its scope and approval remain owned by TAK-2. These additions are outside the fixed 278-path baseline ledger.

## TAK-9 continuation, 2026-10-12

### P0-06 â€” HIGH: doctor changed the database it was diagnosing

`cli.doctor` called `Repository.migrate()`. A synthetic schema-9 database with a preserved product row, fake Telegram Bot and fake Playwright reproduced the contract breach: `doctor` returned `SQLite: OK` and advanced `PRAGMA user_version` to 10. The RED test is `tests/test_doctor_read_only.py::test_doctor_does_not_upgrade_existing_schema`. The candidate now opens the existing database in SQLite read-only mode, checks its version and reports `SQLite: blocked (schema update required)` without migrating or reseeding it. Focused GREEN and lint evidence is in [verification.md](verification.md). The test is a synthetic diagnostic; no private database was opened.

### P0-07 â€” HIGH: actual CI ACL failure remains open

[Run 38268644004, job 114877125611](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38268644004/job/114877125611) completed with 29 failed and 1629 passed tests. The failed nodes depend on Windows private-tree ACL verification; Ruff and diff checks passed, and wheel stages were skipped. A local synthetic scratch run passed, so the mismatch required runner evidence. Do not weaken ACL expectations or call CI green.

The first diagnostic candidate, `e64fca0`, reached [run 38272674378](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38272674378) but stopped before pytest: direct `scripts/ci_acl_probe.py` execution lacked the repository import path on that host. The workflow now invokes the probe as a module; this is an entry-point correction, not an ACL repair.

[Run 38273126818 at `24611ca`](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38273126818) completed with 29 failed, 1630 passed in 341.32s. Its sanitized scratch probe established the mismatch: `owner_matches=False` while the single allow rule had the correct user SID, full rights, inheritance and propagation. Both batch and single-path ACL verification failed for that reason. The candidate now sets the file/directory owner to the authenticated user SID before committing the DACL, then retains exact owner and rule readback. [Run 38275905585 at `efc4f03`](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38275905585) proved the repair on the CI runner: sanitized batch and single-path owner/rule readback passed, and 1660 tests passed. Its one failure was a new doctor test fixture that created a database after securing the private tree, so read-only doctor correctly refused its inherited CI ACL. The synthetic fixture now explicitly secures that file before the no-write assertion; focused ACL/doctor tests pass locally. Corrected-candidate CI at `43e58c1` passed 1661 offline tests, ACL diagnostic, Ruff, whitespace and installed-wheel smoke; see [verification.md](verification.md).

The subsequent documentation-head [CI run 38282736456, job 114923683151](https://github.com/Adolfoderueda/project_shop_assistant/actions/runs/38282736456/job/114923683151) at `6aebec19e55c7da50105a02cd9ccab413cc7f8b3` also completed successfully: 1661 offline tests in 561.40s, Ruff, whitespace, synthetic ACL diagnostic and installed-wheel smoke. This closes the CI repair verification at that SHA; it does not close the manual audit or release gates.

### P0-08 â€” HIGH: doctor entered a filesystem ACL writer (repair verified in CI)

Static trace after the initial schema repair: `cli.py:101` called `load_settings(root)`; `config.py:244` invoked `_private_tree(root / "private")`, applying ACLs to every path. Synthetic RED tests caught that write path and a foreign ACL grant that doctor silently repaired before diagnosis. The candidate now calls `load_settings(read_only=True)`, which preflights links and reads effective owner-only ACLs without applying them. A foreign grant blocks the diagnostic and remains unchanged. Focused tests and full candidate CI passed; independent review remains pending.

### Seven-package native-agent reconciliation against the merged baseline

The October 8 implementation plan, spec, merged commit history and named test files show these packages are present. Presence and test execution do not close the remaining manual owned-path audit or the real-model release gate. Existing interfaces are retained; migration 009 is already merged and remains untouched.

| Package | Merged implementation / origin | Relevant tests | Remaining evidence |
| --- | --- | --- | --- |
| 1. Contracts and fixed skills | `shopping_agent/contracts.py`, `skills.py`, four packaged skills and MIT notice; `edf1d2b` | `test_agent_contracts.py`, `test_agent_skills.py` | Independent detailed source review pending. |
| 2. Pure proposals and replies | `shopping_agent/proposals.py`, `replies.py`; `4bbe76e` | `test_agent_proposals.py`, `test_agent_replies.py` | Real semantic selection and duplicate interpretation still fail historically. |
| 3. Atomic persistence and provenance | `shopping_agent/storage.py`, existing `migrations/009.sql`, repository mixin; `5cc7107` plus provenance fixes | `test_agent_storage.py`, `test_agent_recovery.py`, `test_command_query_provenance.py` | Full audit of stale/foreign/expired and recovery paths pending; no migration reuse. |
| 4. Seven controlled tools | `shopping_agent/tools.py`; `75dd652` | `test_agent_tools.py` | Real E4B can choose a valid but wrong tool; historical quality gate remains. |
| 5. Bounded local E4B loop | `shopping_agent/ollama.py`; `6f7b681` | `test_agent_ollama.py` | No new real-model run is authorized in this audit. |
| 6. Opt-in routing and rollback | `shopping_agent/conversation.py`, `runtime.py`, `cli.py`, `dialogue_storage.py`; `55d8997` and later fixes | `test_agent_conversation.py`, `test_agent_runtime.py`, `test_agent_route_notices.py` | The diagnosed ACL owner mismatch is repaired and actual CI passed at `43e58c1`; independent review remains pending. |
| 7. Offline and real acceptance | `scripts/probe_skills_agent.py`, end-to-end/probe tests and archived JSONL; `2df0d08` | `test_agent_end_to_end.py`, `test_agent_probe.py` | Two frozen real runs each passed 50/53 steps; saved-list query and internal-duplicate completion failed. Guided v5 quality also remains failing. No Telegram acceptance. |

