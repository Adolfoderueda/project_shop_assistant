# Baseline audit — started, incomplete

Observed 2026-10-12. Owner: Mushu. Independent reviewer: pending staffing. Work: GitHub #5 / Paperclip TAK-3. Tracking: #4.

## Corrected baseline

Remote default branch is feat/shop-assistant at b9a29049160cc53737d1cb64a8138385aa2fedd2. Local planning checkout is 0594bf0247bcdef35656f2ead5bf3d054263e17b. Merged PR #3 already includes shopping_agent, skills, guided questions and migrations. The approved plan is preserved verbatim in plan.md; its historical repository observations are superseded by this audit evidence, not a change to the approved outcome or gates. Reconcile the existing implementation before P1 development. Do not allocate migration 009 without inspecting the current sequence.

Inventory: 278 tracked paths. No AGENTS.md or GitHub workflows found in the remote tree. No open PRs, existing engineering issues or milestones found before setup. Six epic/package issues combine epic and executable package tracking to avoid redundant tickets.

## Fresh verification

An isolated archive of the exact remote SHA was inspected with the existing project Python environment; no private configuration or live services were used.

- python -m ruff check <isolated archive>: exit 0, All checks passed.
- python -m pytest --collect-only -q from archive root: exit 0, 1658 tests collected in 2.84s.
- Collection is not test execution. Full pytest is pending on TAK-3.
- build, wheel and setuptools are absent from the existing environment. Offline wheel build/installation verification remains pending; do not claim packaging passed or install dependencies without checking the applicable gate.
- GitHub workflows count: 0. CI remains unestablished.
- GitHub reports default branch protected=false. Protection and rulesets endpoints return 403 requiring GitHub Pro or a public repository. No visibility/subscription change was made. Preserve manual review and merge gate.

## Findings and retained limits

1. High-priority planning correction: local checkout missed the merged native-agent implementation. Audit the actual remote baseline and reuse existing work.
2. Packaging candidate: product_memory.py exists but is absent from explicit py-modules in current pyproject.toml. Installed-wheel reproduction still pending; do not call this a verified runtime failure.
3. Existing evidence records E4B quality failures and pending live Telegram acceptance. A later callback correction has offline evidence but real-model acceptance was not repeated. Historical results are not current verification.
4. CI and enforceable branch protections are absent. Independent review and Takeshi merge/activation gates remain mandatory.

## Next execution

TAK-3 must finish full pytest, every-path review, packaging reproduction, CI proposal/run evidence, reproducible defect records and independent QA handoff. Preserve sensitive data boundaries and use synthetic state only. P1 is blocked by P0 and staffing; no full-code audit completion is claimed here.

## Path coverage

This inventory is a coverage ledger, not a claim that all paths were read. Review each pending path and record finding/test evidence before completing P0.

| Path | Review status |
| --- | --- |
| .gitignore | Pending |
| .superpowers/sdd/2026-09-27-asistente-compras/final-fix-report.md | Pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/final-fix-report.md | Pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/task-1-report.md | Pending |
| .superpowers/sdd/2026-09-29-gemma4-local-telegram/task-2-report.md | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-focused-final.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-full.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-green.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-product-red-corrected.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-real-exits.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-red-corrected.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-report.md | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-ruff.txt | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-5-report.md | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-6-report.md | Pending |
| .superpowers/sdd/2026-10-08-agente-skills-herramientas/task-7-report.md | Pending |
| .superpowers/sdd/2026-10-08-dialogo-natural-altas-incrementos/task-6-report.md | Pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/focused.txt | Pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/full.txt | Pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/green.txt | Pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/red.txt | Pending |
| .superpowers/sdd/2026-10-09-callback-cancel-reset/report.md | Pending |
| README.md | Pending |
| catalog.py | Pending |
| checkout.py | Pending |
| checkout_storage.py | Pending |
| cli.py | Pending |
| config.py | Pending |
| conversation.py | Pending |
| dialogue.py | Pending |
| dialogue_additions.py | Pending |
| dialogue_controller.py | Pending |
| dialogue_increments.py | Pending |
| dialogue_replies.py | Pending |
| dialogue_requests.py | Pending |
| dialogue_storage.py | Pending |
| docs/setup.md | Pending |
| docs/store-capabilities.md | Pending |
| docs/superpowers/continuacion-gemma-2026-10-01.md | Pending |
| docs/superpowers/continuacion-gemma-lista-2026-09-30.md | Pending |
| docs/superpowers/continuacion-telegram-2026-09-28.md | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/README.md | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/execution-status.md | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl | Pending |
| docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md | Pending |
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
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/results.md | Pending |
| docs/superpowers/evidence/2026-10-09-e4b-native-quality/trials.jsonl | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v3-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v4-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v5-freeze.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v2.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v3.json | Pending |
| docs/superpowers/evidence/2026-10-09-preguntas-guiadas/execution-status.md | Pending |
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
| docs/superpowers/specs/2026-10-08-agente-skills-herramientas-design.md | Pending |
| docs/superpowers/specs/2026-10-08-dialogo-natural-altas-incrementos-design.md | Pending |
| docs/superpowers/specs/2026-10-08-respuestas-naturales-gemma-design.md | Pending |
| docs/superpowers/specs/2026-10-09-preguntas-guiadas-telegram-design.md | Pending |
| docs/superpowers/task-8-report.md | Pending |
| domain.py | Pending |
| interpreter.py | Pending |
| migrations/001.sql | Pending |
| migrations/002.sql | Pending |
| migrations/003.sql | Pending |
| migrations/004.sql | Pending |
| migrations/005.sql | Pending |
| migrations/006.sql | Pending |
| migrations/007.sql | Pending |
| migrations/008.sql | Pending |
| migrations/009.sql | Pending |
| migrations/010.sql | Pending |
| migrations/__init__.py | Pending |
| offers.py | Pending |
| ollama_interpreter.py | Pending |
| ollama_replies.py | Pending |
| presentation.py | Pending |
| presentation_phrases.py | Pending |
| presentation_replies.py | Pending |
| presentation_storage.py | Pending |
| presentation_validation.py | Pending |
| product_memory.py | Pending |
| pyproject.toml | Initial inspection; full audit pending |
| recovery.py | Pending |
| requirements.lock | Pending |
| restrictions.py | Pending |
| runtime.py | Pending |
| scripts/Install-ShopAssistant.ps1 | Pending |
| scripts/Probe-Dialogue.ps1 | Pending |
| scripts/Probe-NaturalDialogue.ps1 | Pending |
| scripts/Probe-Replies.ps1 | Pending |
| scripts/Start-ShopAssistant.ps1 | Pending |
| scripts/Stop-ShopAssistant.ps1 | Pending |
| scripts/Uninstall-ShopAssistant.ps1 | Pending |
| scripts/diagnose_guided_native_v2.py | Pending |
| scripts/probe_guided_questions.py | Pending |
| scripts/probe_skills_agent.py | Pending |
| shop_assistant/__init__.py | Pending |
| shop_assistant/__main__.py | Pending |
| shopping_agent/__init__.py | Pending |
| shopping_agent/contracts.py | Pending |
| shopping_agent/conversation.py | Pending |
| shopping_agent/guided_contracts.py | Pending |
| shopping_agent/guided_controller.py | Pending |
| shopping_agent/guided_conversation.py | Pending |
| shopping_agent/guided_ollama.py | Pending |
| shopping_agent/guided_replies.py | Pending |
| shopping_agent/guided_storage.py | Pending |
| shopping_agent/ollama.py | Pending |
| shopping_agent/proposals.py | Pending |
| shopping_agent/replies.py | Pending |
| shopping_agent/skills.py | Pending |
| shopping_agent/skills/altas.md | Pending |
| shopping_agent/skills/cambios.md | Pending |
| shopping_agent/skills/consultar.md | Pending |
| shopping_agent/skills/propuestas.md | Pending |
| shopping_agent/storage.py | Pending |
| shopping_agent/tools.py | Pending |
| storage.py | Pending |
| stores/__init__.py | Pending |
| stores/amascotados.py | Pending |
| stores/base.py | Pending |
| stores/browser.py | Pending |
| stores/charro.py | Pending |
| stores/connections.py | Pending |
| stores/mercadona.py | Pending |
| stores/nappy.py | Pending |
| stores/public.py | Pending |
| stores/registry.py | Pending |
| telegram_io.py | Pending |
| tests/__init__.py | Pending |
| tests/agent_support.py | Pending |
| tests/dialogue_support.py | Pending |
| tests/factories.py | Pending |
| tests/fakes.py | Pending |
| tests/fixtures/stores/amascotados.html | Pending |
| tests/fixtures/stores/charro.html | Pending |
| tests/fixtures/stores/mercadona-search.html | Pending |
| tests/fixtures/stores/mercadona.html | Pending |
| tests/fixtures/stores/nappy-out.html | Pending |
| tests/fixtures/stores/nappy.html | Pending |
| tests/guided_helpers.py | Pending |
| tests/stores/test_amascotados.py | Pending |
| tests/stores/test_browser.py | Pending |
| tests/stores/test_charro.py | Pending |
| tests/stores/test_contract.py | Pending |
| tests/stores/test_mercadona.py | Pending |
| tests/stores/test_nappy.py | Pending |
| tests/stores/test_public_adapters.py | Pending |
| tests/test_agent_contracts.py | Pending |
| tests/test_agent_conversation.py | Pending |
| tests/test_agent_end_to_end.py | Pending |
| tests/test_agent_ollama.py | Pending |
| tests/test_agent_probe.py | Pending |
| tests/test_agent_proposals.py | Pending |
| tests/test_agent_recovery.py | Pending |
| tests/test_agent_replies.py | Pending |
| tests/test_agent_route_notices.py | Pending |
| tests/test_agent_runtime.py | Pending |
| tests/test_agent_skills.py | Pending |
| tests/test_agent_storage.py | Pending |
| tests/test_agent_tools.py | Pending |
| tests/test_checkout.py | Pending |
| tests/test_command_query_provenance.py | Pending |
| tests/test_conversation.py | Pending |
| tests/test_dialogue.py | Pending |
| tests/test_dialogue_conversation.py | Pending |
| tests/test_dialogue_end_to_end.py | Pending |
| tests/test_dialogue_increments.py | Pending |
| tests/test_dialogue_quantity_bounds.py | Pending |
| tests/test_dialogue_replacement.py | Pending |
| tests/test_dialogue_requests.py | Pending |
| tests/test_dialogue_storage.py | Pending |
| tests/test_end_to_end.py | Pending |
| tests/test_guided_acceptance.py | Pending |
| tests/test_guided_callback_cancel_reset.py | Pending |
| tests/test_guided_contracts.py | Pending |
| tests/test_guided_controller.py | Pending |
| tests/test_guided_conversation.py | Pending |
| tests/test_guided_events.py | Pending |
| tests/test_guided_final_fixes.py | Pending |
| tests/test_guided_migration.py | Pending |
| tests/test_guided_native_integration.py | Pending |
| tests/test_guided_ollama.py | Pending |
| tests/test_guided_provenance.py | Pending |
| tests/test_guided_replies.py | Pending |
| tests/test_guided_runtime.py | Pending |
| tests/test_guided_storage.py | Pending |
| tests/test_guided_telegram_io.py | Pending |
| tests/test_migration_distribution.py | Pending |
| tests/test_natural_dialogue_probe.py | Pending |
| tests/test_natural_dialogue_runtime.py | Pending |
| tests/test_natural_presentation.py | Pending |
| tests/test_offers.py | Pending |
| tests/test_ollama_interpreter.py | Pending |
| tests/test_ollama_replies.py | Pending |
| tests/test_pending_additions.py | Pending |
| tests/test_presentation_replies.py | Pending |
| tests/test_presentation_storage.py | Pending |
| tests/test_presentation_validation.py | Pending |
| tests/test_private_acl.py | Pending |
| tests/test_product_memory.py | Pending |
| tests/test_product_queries.py | Pending |
| tests/test_recovery.py | Pending |
| tests/test_reply_conversation.py | Pending |
| tests/test_reply_probe.py | Pending |
| tests/test_reply_runtime.py | Pending |
| tests/test_runtime.py | Pending |
| tests/test_storage.py | Pending |
| tests/test_telegram_io.py | Pending |
| third_party/shopping-list-skill/LICENSE | Pending |
| third_party/shopping-list-skill/NOTICE.md | Pending |