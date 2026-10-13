# TAK-9 consolidated batch manifest

Prepared 2026-10-13 by Alpha for Puente [TAK-23](/TAK/issues/TAK-23) and Izpi [TAK-11](/TAK/issues/TAK-11). Engineering record: [GitHub #13](https://github.com/Adolfoderueda/project_shop_assistant/issues/13); publication target: draft [PR #11](https://github.com/Adolfoderueda/project_shop_assistant/pull/11).

- Fixed product baseline: `b9a29049160cc53737d1cb64a8138385aa2fedd2` (278 tracked blobs).
- Local source immediately before this dossier: `fb200914ef1b13247e5cc7ca4741fbbf980930bf`. The dossier commit itself is reported in TAK-9 and GitHub #13 after creation, avoiding a self-referential SHA. Puente records source-to-integrated SHA in TAK-23.
- Last verified remote PR #11 head before this dossier: `43a797f1d0e4ba1db084529bc0c87ccbe25f2773`, Windows run 38358039399 success. This is not the final dossier CI.
- Baseline ledger: 278 unique rows, 263 direct reviews and 15 attributed TAK-10 store fixture/test reviews; zero path differences. The TAK-10 report covers all 30 store-scope paths, [PR #16](https://github.com/Adolfoderueda/project_shop_assistant/pull/16) head `b4b8e279bc6b2acc67a237cca1e2c984dabb1370`, report blob `d9d640726f6d71718dfc7ccbe81d12684a3ba4dc`. Local baseline store paths are unchanged. QA and that PR's CI remain open.
- Historical evidence: [JSONL manifest](evidence-manifest.json) lists 36 files, 7,349 parsed records, 118,909,971 checkout bytes, zero parse errors and exact checkout SHA-256. Git blob hashes below identify the baseline bytes independently of Windows line endings.

## Findings and owners

| ID | Severity / disposition | Next owner |
| --- | --- | --- |
| P0-01 installed wheel | HIGH, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| P0-02 archive line endings | MEDIUM, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| P0-03 guided temp path | MEDIUM, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| P0-04 native/guided semantic quality | HIGH release gate open; historical real acceptance fails | TAK-4 functional owner, then Izpi/Takeshi |
| P0-05 CI/governance | Open until this dossier's integrated SHA has CI and independent QA | Puente TAK-23; Izpi TAK-11 |
| P0-06 doctor DB mutation | HIGH, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| P0-07 Windows ACL CI | HIGH, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| P0-08 doctor ACL writer | HIGH, repaired and previously CI tested | Puente final exact-SHA CI; Izpi QA |
| TAK-10 pack identity | HIGH, RED/137 focused PASS in separate PR #16; integration/review pending | Store engineer, Puente, Izpi |
| TAK-10 partial search, empty result, historical-only ficha | MEDIUM P3 handoffs; no current public price | TAK-6/store engineer and Mushu interface routing |

## Required handoff

Puente: compare PR head before writing; integrate the dossier through TAK-23 as one remote writer; preserve concurrent work and record each source commit to result commit; run complete offline suite, Ruff, diff, ACL and installed wheel at the final PR SHA. Izpi: review the exact resulting diff, store report, real/synthetic evidence boundaries and open findings in TAK-11. Real-model quality and Telegram remain PENDING; no activation, merge or acceptance is implied.

## Baseline path to blob map

Each object ID is the exact Git blob at the fixed baseline. "Direct" means the ledger has a source/structured-evidence review by Alpha/Mushu; "TAK-10 delegated" means the store engineer's delivered full-source review.

| Baseline path | Git blob SHA-1 | Review source |
| --- | --- | --- |
| `.gitignore` | `70289c134298e698e1d570e0aa23c1a4e09d06a4` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-09-27-asistente-compras/final-fix-report.md` | `b6999fe0dc233847a6b37fac4c0c14f8c4b15c74` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-09-29-gemma4-local-telegram/final-fix-report.md` | `5a4acc636e9bf3b0eca03fddebbad47d36510739` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-09-29-gemma4-local-telegram/task-1-report.md` | `3945afa25337ab907bbc9221711d0e4bb459f12b` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-09-29-gemma4-local-telegram/task-2-report.md` | `e6b0b0d99b88539c522eebbf0b92d08ed98052d9` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-focused-final.txt` | `cb846d2bb11b06306f3d52117b6d793c4e621499` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-full.txt` | `04b828a797269b960e8c1d85dd59a78c2a4dae24` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-green.txt` | `19566688d8f4b5680a2258c29223c22da4f01007` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-product-red-corrected.txt` | `6ab172974bac744f1d1bd8c8586934eed9ff68cf` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-real-exits.txt` | `5c77549fa8a0715ec7c2fc622d5a4f57e8637995` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-red-corrected.txt` | `dfe5c66f8a414b49992db33fac06a99f94753cc5` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-report.md` | `6f68669e80ae8d2609096e950b77584d4d2acbb9` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/final-fix-ruff.txt` | `e0a208c2b0bbc0ae4da1698ccdd0313c486c0db9` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/task-5-report.md` | `417e1199958527c024ecc6c346e6d8512fb0d2bd` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/task-6-report.md` | `9ea470d89a750eb3c45cb4be16d1be536cb253dc` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-agente-skills-herramientas/task-7-report.md` | `3e06fe70770991a5021715629e22cbb3ea841958` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-08-dialogo-natural-altas-incrementos/task-6-report.md` | `1b058db159da0a7939e888eae5b4a82538dbea5a` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-09-callback-cancel-reset/focused.txt` | `79d5226da8f5ecd04ab028957cbcba62696eea3f` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-09-callback-cancel-reset/full.txt` | `c1c35de5448ccd2e9f4c9d413eeb0080baaae57e` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-09-callback-cancel-reset/green.txt` | `10bae4915c153d7976a68d6e5e1e02b630cd036d` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-09-callback-cancel-reset/red.txt` | `cc81d67b581f38cd6a9fcdcac10ed69b1c3c7bd2` | Alpha/Mushu direct |
| `.superpowers/sdd/2026-10-09-callback-cancel-reset/report.md` | `00c5917a8cefaa58ae6dbb1185c18b46dfd97ab4` | Alpha/Mushu direct |
| `README.md` | `d599af15c4224e192f48905ca9e86161332af4d7` | Alpha/Mushu direct |
| `catalog.py` | `f3a438c650f83b6a91271200084f0ed2b73664da` | Alpha/Mushu direct |
| `checkout.py` | `7593a91326e1e4e752b2058a103a813b46dd51c5` | Alpha/Mushu direct |
| `checkout_storage.py` | `a1db8395c38791d511fb7e84eaefb6f5ae323811` | Alpha/Mushu direct |
| `cli.py` | `4482498ae32b6dfe74a46d736343189784bb5221` | Alpha/Mushu direct |
| `config.py` | `3b1a7b6b12cba47df86729a017494ddc01596d15` | Alpha/Mushu direct |
| `conversation.py` | `995cfde60f7b29d7506901c7ea07e3565ec0ee0f` | Alpha/Mushu direct |
| `dialogue.py` | `558f909f20a877160487935b0afc2019cf124378` | Alpha/Mushu direct |
| `dialogue_additions.py` | `644142278c932d86dedf93ae0951a56d5f4e07fc` | Alpha/Mushu direct |
| `dialogue_controller.py` | `aeaec8bb8325072a39518221224d0e227194eec5` | Alpha/Mushu direct |
| `dialogue_increments.py` | `2804e782b945d1aab54c860d86db49b54141a68f` | Alpha/Mushu direct |
| `dialogue_replies.py` | `7c8eb11103628364a3ad1333f94c38dcef5288ea` | Alpha/Mushu direct |
| `dialogue_requests.py` | `0edace0b336ac54503972693e840695e34b60698` | Alpha/Mushu direct |
| `dialogue_storage.py` | `14c103529659c0c66f293226d3ec4008077eadb0` | Alpha/Mushu direct |
| `docs/setup.md` | `45307488d930fb2845c97ae69699e1441f768887` | Alpha/Mushu direct |
| `docs/store-capabilities.md` | `0e66c645e88c55784c93d64677d138b9b39a8e5b` | Alpha/Mushu direct |
| `docs/superpowers/continuacion-gemma-2026-10-01.md` | `850a307f391386ace33b3f3192a85d72c0dcc979` | Alpha/Mushu direct |
| `docs/superpowers/continuacion-gemma-lista-2026-09-30.md` | `980658212243dca24a55e8e5f43b66c72d914e6e` | Alpha/Mushu direct |
| `docs/superpowers/continuacion-telegram-2026-09-28.md` | `eb5d70326bd3bd999b5dc0ad3766db650dc16f3d` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/README.md` | `49a2e743f4b435acc2345bdc8a64cde0a12412ac` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/execution-status.md` | `d1234cb80acf77b80c406b76acf93ddbb1a16424` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-1.jsonl` | `4bf411de969a07f71260fb5b627b45d5b096245a` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-real-2.jsonl` | `970ae0f638c2067efacd995a7aa18075a2168ada` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/final-review-summary.md` | `da9eb8c0b155d201319908c79e30595f938433bd` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix-round-1.md` | `758bc210e39bee6ba0dd79bba377a35ee9344f07` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-offline.jsonl` | `f59aa92c56422e32372b22cf0585a907d6dc3970` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-1.jsonl` | `75ab5d102f966b0dd96ab72919891894115bff16` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-final-real-2.jsonl` | `face3ab42ce30cacc5c03a18aab11088b87ce8f9` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-control.jsonl` | `7131fa7cddd8e312ff2d3ec57476704387ecc950` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h1-recipe.jsonl` | `c9eedeca4b6a54820afd5ef28e6959cd5618d000` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-control.jsonl` | `d858446d1881fef12d62d1a969e61fa99035a589` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-full-real.jsonl` | `6edeefaa99cd290888fea1b134f58675207824c9` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h2-recipe.jsonl` | `2d23fc8b0697702f5fbb8df3d2e090204db48b72` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-contract.jsonl` | `7b11aa12cb43d8db0bdd03a954cf7dfceeb07e1e` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-control.jsonl` | `c483b25905bcd56e50079b55f44f11133d21da2b` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-contract.jsonl` | `2d5201efc8a5ee3bc3fb1c8a20539b0b86ca61a8` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h3-realistic-control.jsonl` | `e7ad1728449a88017bdd9c8bdc7a7fac3c019450` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-full-real.jsonl` | `9231243d9dc5508a516676cebd979c392ddee860` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-h4-scope.jsonl` | `ced5e7a80305ae91a2217f95f737637dd7d350a5` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/fix1-schema-only-real.jsonl` | `9f5b89b612f93cd1654bc1121abac8513ac32f2a` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-1.jsonl` | `7265cc28b68f03ffbc86c9733ad50bbc418d1c8e` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/frozen-real-pass-2.jsonl` | `09bb1661e5d58f4bc6f052b36ead6f898ce699d4` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/offline.jsonl` | `62477dc4518acd2e545f8e3f897c338613a4398d` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/real-pass-1.jsonl` | `1d2fc153df7627e99b9842104fb5f1f27484f075` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/schema-diagnostic.jsonl` | `b037cbd5cb8e8e9d5bed56874f41138ec68181cb` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/skill_micro_probe.py` | `79f5d59c949b9f20fa1451518152052da28477a7` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-08-skills-agent/verification.txt` | `112aa0e51c8da481d5cc8afda1458e6960956986` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-e4b-native-quality/.gitattributes` | `463ad9a9f64f0e89c7bd7c538430879d267597d5` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-e4b-native-quality/preregistration.json` | `77c8e9355e808524ba40a39e6cabe86fae553c0f` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-e4b-native-quality/results.md` | `a4766d386cf00abb6c08b726cea01849e6ae405f` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-e4b-native-quality/trials.jsonl` | `725dcd5e8de398474de58a0103a20ea2737cd136` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v3-freeze.json` | `2e1fe15133ba42aef72118a22c46a9a8a0605a59` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v4-freeze.json` | `afe582245f81cb9d993a5457e09a49cbdc7c728b` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/acceptance-v5-freeze.json` | `5cbdfd940d1478425660b90c8eaf75628ad8db95` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v2.json` | `2ccd13816ec17ed0662a7463b37e318b3949103f` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/archive-v3.json` | `7ffe92d04dce79109d4093ca3554435a2beb5014` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/execution-status.md` | `c798408db0962191a61bdf96b0e1214b906f0980` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v3.md` | `113cf5c5e4b6036775264d7656fc4842159cb797` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v4.md` | `4a085749bd82762d59b964642c290a793f9e5db8` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/final-fixes-v5.md` | `8457125ffc1944a8f8d5b29ee512ac53796cf507` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/handoff.md` | `ce761fddc1ea5befd3831f9303c3d231802e639e` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json` | `29c7db6714b4c33695806a7ccc17387741b5b272` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v4.json` | `da5d3478def63c89e00daec309026526d5eea493` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v5.json` | `d13894dc47ce67654887184d7c45f15bfbe0163e` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix.json` | `1e1daa0d598d694bb34c76e587850e2c5602f041` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1-source.txt` | `7cbffe43183c0cd421b9de190d7e0014e3253446` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v1.jsonl` | `63148b00c23aa5ec4ebd00c6a981f4814fd7705d` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/native-diagnosis-v2.jsonl` | `9b00a8add73c963c178fe7d289b40a3dcf5fef7d` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v2.jsonl` | `01f9793bba52dfd19aa3a45f0571ff40dcc9347b` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v3.jsonl` | `40d3462d19edd16950e789cec9fa45e64d634cec` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v4.jsonl` | `f7f6ad90dcefd54fba537ecaf7787d4f54d10c6b` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v5.jsonl` | `624dfbd2df2e8eaed83d558e60fefcde6b60bd91` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v2.jsonl` | `3edbd633000c2531e4145f0a9f1a80121ff1b53a` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v3.jsonl` | `9deeca469a5c794b4302fab1d18485b3a98d6159` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v4.jsonl` | `4e8eef73eecf85b8080abf2eff07a7a13fcdfef2` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v5.jsonl` | `877396864c3cd2d68863514367a96f73f52b4c5e` | Alpha/Mushu direct |
| `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/results.md` | `2b7499aa44dd99421e98f7db35293b93413cd22c` | Alpha/Mushu direct |
| `docs/superpowers/gemma4-12b-local-2026-10-10.md` | `36ef36286122499b5e58bea26d4424924650e658` | Alpha/Mushu direct |
| `docs/superpowers/natural-dialogue-real-2026-10-08-run1.jsonl` | `eea34b50a06c21abd95d0f382bfbd5b77d831d4c` | Alpha/Mushu direct |
| `docs/superpowers/natural-dialogue-real-2026-10-08-run2.jsonl` | `0dcd1157c1a3ff9f9f8d21b1559101722a5b0956` | Alpha/Mushu direct |
| `docs/superpowers/natural-dialogue-real-2026-10-08-run3.jsonl` | `3652b1c458627cfbb5f79ee06b669dba83a3c7ec` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-09-27-asistente-compras.md` | `05284a1e00c0d96fb6dd07669983e47a5e90418c` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-09-29-gemma4-local-telegram.md` | `667fc7f031bb178e19bfce17f7ec5911a7fb64f7` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-09-29-lista-fichas-gemma.md` | `7fc33cd9f4394997de5857f2ca25e3c8d52f5995` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-10-01-conversacion-contextual-gemma.md` | `f5eb89ea06e19b54e661dbea3318f8981540a80f` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-10-08-agente-skills-herramientas.md` | `cd1c1e7f79161a96f171cc7db1a80f80519bb1bc` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-10-08-dialogo-natural-altas-incrementos.md` | `147f38cd6958f87a16fae1ff710a962d7328be61` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-10-08-respuestas-naturales-gemma.md` | `26b8d1649391b1c16ba1012afa8763bd917ff3c6` | Alpha/Mushu direct |
| `docs/superpowers/plans/2026-10-09-preguntas-guiadas-telegram.md` | `5b5893604135178d03803f429fdc01641d16ad65` | Alpha/Mushu direct |
| `docs/superpowers/progress.md` | `0736b021e9efaf25bc1b1bd734d7a4e6c1c72e8b` | Alpha/Mushu direct |
| `docs/superpowers/prueba-dialogo-contextual-2026-10-01.md` | `d882b1626b033311df294312027f673420c8e923` | Alpha/Mushu direct |
| `docs/superpowers/prueba-dialogo-natural-2026-10-08-run3.md` | `48eaa0f6aa85b762df6f2b5e7aeed77ea59c8c29` | Alpha/Mushu direct |
| `docs/superpowers/prueba-dialogo-natural-2026-10-08.md` | `7c3b8977c00226f5404fc36690f1fdf51c4706c0` | Alpha/Mushu direct |
| `docs/superpowers/prueba-gemma-2026-10-01.md` | `2ae847e5fecc299d328336da59bfc1874a09c4b2` | Alpha/Mushu direct |
| `docs/superpowers/prueba-respuestas-gemma-2026-10-08.md` | `3430620f9a5267fe501a026d9c5fd243d7b65d2f` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-09-27-asistente-compras-design.md` | `8a1aed3c3f312b65d0a8d583a51e1043e2c80cb0` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-09-29-gemma4-local-telegram-design.md` | `c449fb2e64a51ae9e3c2ca77d0eb68755f27cfb1` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-09-29-lista-fichas-gemma-design.md` | `6c030a4db2d0588b965024eeff964ae58479aa16` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-10-01-conversacion-contextual-gemma-design.md` | `63158b631996359066ecd507285b974360b93bad` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-10-08-agente-skills-herramientas-design.md` | `d1cc22156ccd183b48e498c4d6108f28231c33a1` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-10-08-dialogo-natural-altas-incrementos-design.md` | `72d40cd1d9fd6115979bde215a810d1dd6ad4108` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-10-08-respuestas-naturales-gemma-design.md` | `c0020cb9aad3f5c4d5bce36617fdc0f9087e3637` | Alpha/Mushu direct |
| `docs/superpowers/specs/2026-10-09-preguntas-guiadas-telegram-design.md` | `bac71d647fea1d8c51bba3070be02260063221f3` | Alpha/Mushu direct |
| `docs/superpowers/task-8-report.md` | `3ef90bca744231b0266c58ed54cacb243834124e` | Alpha/Mushu direct |
| `domain.py` | `2dd38f449898d1435aa73f1ae66a79c5519d81e3` | Alpha/Mushu direct |
| `interpreter.py` | `65006c1d2bfeea284a512925f59a8ee5a0fe52b4` | Alpha/Mushu direct |
| `migrations/001.sql` | `e8ab9d48f2a5add8ff10e0299f0bffb667cfdc3a` | Alpha/Mushu direct |
| `migrations/002.sql` | `2dcad7925ce7c436a2cdf87705e5aa001bec6bd7` | Alpha/Mushu direct |
| `migrations/003.sql` | `a19a8763b33fbeaa862347abeed6a0c2f169393b` | Alpha/Mushu direct |
| `migrations/004.sql` | `849692272e770a0dd061b7ef65c4a2a283d95b64` | Alpha/Mushu direct |
| `migrations/005.sql` | `956651e05a8708719445175d755802e01ecb00f0` | Alpha/Mushu direct |
| `migrations/006.sql` | `c44ac676ad66a5db916cd455dd5eedfa365cd11d` | Alpha/Mushu direct |
| `migrations/007.sql` | `f09abc6b9478fddf3ad48fc068cf9d54051bc9a2` | Alpha/Mushu direct |
| `migrations/008.sql` | `f4bbd7140da6c9571d05c586eda1b3259d42257b` | Alpha/Mushu direct |
| `migrations/009.sql` | `e865cdaa95f77c262b7d78e3518821336beb895f` | Alpha/Mushu direct |
| `migrations/010.sql` | `e48c4d02a6406e8140a140abe092b1478d51e094` | Alpha/Mushu direct |
| `migrations/__init__.py` | `e35cc7e95c411e6c36133bc081a64607164db503` | Alpha/Mushu direct |
| `offers.py` | `ce4f4db212fb6409a0a7803859d30fc44e78991f` | Alpha/Mushu direct |
| `ollama_interpreter.py` | `9755832e1aefe08df32d0d1f4dd764cb93bff6d2` | Alpha/Mushu direct |
| `ollama_replies.py` | `bec2a351cedc8954768ab10b4cab9866c0977054` | Alpha/Mushu direct |
| `presentation.py` | `c77d08f8a03dd546e916e556471017857d8d6ae3` | Alpha/Mushu direct |
| `presentation_phrases.py` | `45493a1dd5f81c808dd8dbe3066177dc5021559a` | Alpha/Mushu direct |
| `presentation_replies.py` | `83adfab86607dffc502eed21e91888d54b3186f9` | Alpha/Mushu direct |
| `presentation_storage.py` | `bd3b6e9dd56f5f5cab8f14bdf6cce2fc0b93435e` | Alpha/Mushu direct |
| `presentation_validation.py` | `a9ea050b77a05f4194657823f0f080c282369e0a` | Alpha/Mushu direct |
| `product_memory.py` | `e2d942156d2a0d9186ded80d823ce75e3839c129` | Alpha/Mushu direct |
| `pyproject.toml` | `15eeec35f4448c44829ab408eb011a9990fbf53d` | Alpha/Mushu direct |
| `recovery.py` | `e99ff4ce6e8642d05c2cc545631178e38e5a7585` | Alpha/Mushu direct |
| `requirements.lock` | `86fd4496f1aef4c7c8f2dfd9b996d41385415f74` | Alpha/Mushu direct |
| `restrictions.py` | `dcba7b598e7f5f0b62e7788ade13ae13c8d9dbf4` | Alpha/Mushu direct |
| `runtime.py` | `80352293b71d93b655ab77f950bee77550f70476` | Alpha/Mushu direct |
| `scripts/Install-ShopAssistant.ps1` | `394f3cb1d092ed6f5642ca03785c09b50645356a` | Alpha/Mushu direct |
| `scripts/Probe-Dialogue.ps1` | `e3ea554d96fdd383fc386a699cc0f8cb2daaa5e1` | Alpha/Mushu direct |
| `scripts/Probe-NaturalDialogue.ps1` | `110aa9b521f98db00fdb406fb4826230ce502438` | Alpha/Mushu direct |
| `scripts/Probe-Replies.ps1` | `7a38ffd52f785acec3d9e987c9d642759636a40d` | Alpha/Mushu direct |
| `scripts/Start-ShopAssistant.ps1` | `4f6017163b581015aa23a871c4657d09d26bfab9` | Alpha/Mushu direct |
| `scripts/Stop-ShopAssistant.ps1` | `c2a671712b9cf90a3ea218c071860cb1447a3202` | Alpha/Mushu direct |
| `scripts/Uninstall-ShopAssistant.ps1` | `8fade319d62f6fb972e246b0ae306be1ad2556d7` | Alpha/Mushu direct |
| `scripts/diagnose_guided_native_v2.py` | `9eaeb2215719b77df2edb6589428139b2d9b9c70` | Alpha/Mushu direct |
| `scripts/probe_guided_questions.py` | `fe1c7f5167333ce8dfb27af08b59557acc3cf3da` | Alpha/Mushu direct |
| `scripts/probe_skills_agent.py` | `f55af75a8b5636b43b67d6ee7dbd3e847fad07f6` | Alpha/Mushu direct |
| `shop_assistant/__init__.py` | `ef38f50c202cb37fb9bdb210db33c40f5408a76a` | Alpha/Mushu direct |
| `shop_assistant/__main__.py` | `b0d9c62ba7b561738030ab532586d45d7b832c1b` | Alpha/Mushu direct |
| `shopping_agent/__init__.py` | `d06313d013b529ab4d7a849d5e78c6a6aebdda62` | Alpha/Mushu direct |
| `shopping_agent/contracts.py` | `db2d3d18eeb4ac5ee99bc7ef9e91ce08dccefaab` | Alpha/Mushu direct |
| `shopping_agent/conversation.py` | `2183a688ade8b8f85e8fb8bf3463af287909862a` | Alpha/Mushu direct |
| `shopping_agent/guided_contracts.py` | `7a2bcb9ab005e14cf6cc9903ac0ed23e3f8da787` | Alpha/Mushu direct |
| `shopping_agent/guided_controller.py` | `8d16be85b88b0a5b37e7560741768f48a9acc97c` | Alpha/Mushu direct |
| `shopping_agent/guided_conversation.py` | `c25e2a3317705c5377b69c957f9077583b73376a` | Alpha/Mushu direct |
| `shopping_agent/guided_ollama.py` | `e3f2ac10e5e480867ebe0623d5c00ccafa2d1628` | Alpha/Mushu direct |
| `shopping_agent/guided_replies.py` | `062391a29de9fb3efa2a396922a3893250cf0279` | Alpha/Mushu direct |
| `shopping_agent/guided_storage.py` | `aec26e879a312085528b5aaa9fd9910c8965da54` | Alpha/Mushu direct |
| `shopping_agent/ollama.py` | `fa369ffa64a70ece757f30ca32615332a147196a` | Alpha/Mushu direct |
| `shopping_agent/proposals.py` | `629e32cafe422e456a38226cc866e53a28e0fcbd` | Alpha/Mushu direct |
| `shopping_agent/replies.py` | `56556a74f3ca0cc0147a9ecf8d805b57e1936b66` | Alpha/Mushu direct |
| `shopping_agent/skills.py` | `528fb51197f9624fb2868357c4b47339c9afba42` | Alpha/Mushu direct |
| `shopping_agent/skills/altas.md` | `e4e96249b4ac34ea7a4b3b2d35ee4715a854ba30` | Alpha/Mushu direct |
| `shopping_agent/skills/cambios.md` | `34ae099e468db9e760ab9473d01bbc28e0ce4ce1` | Alpha/Mushu direct |
| `shopping_agent/skills/consultar.md` | `f249a43b399da97e0615298234d6196916ec7870` | Alpha/Mushu direct |
| `shopping_agent/skills/propuestas.md` | `ef5ae4aca82d5bd643d405e5e1dbf1dcf454ae8e` | Alpha/Mushu direct |
| `shopping_agent/storage.py` | `da1c98bb4a2351de0b874e3858f3abfd2588a3f1` | Alpha/Mushu direct |
| `shopping_agent/tools.py` | `0450e2464a8d062da37cf402f9545e20ab79a485` | Alpha/Mushu direct |
| `storage.py` | `fb81d80ffa523ee15f69a43a9981e12edf1e4125` | Alpha/Mushu direct |
| `stores/__init__.py` | `21b9f5964b70ea79ca25405755610f566cd72832` | Alpha/Mushu direct |
| `stores/amascotados.py` | `760c5a1d7c74ad1d86a34db01cc5971479a54d04` | Alpha/Mushu direct |
| `stores/base.py` | `79c5ba404b77468c039f5771f7ee2b55a3f4ae21` | Alpha/Mushu direct |
| `stores/browser.py` | `0dec49d60f9b8f01df4e938100a63cbb164f9887` | Alpha/Mushu direct |
| `stores/charro.py` | `4ca8ccc2ba538e788540a79eb9246c626c886024` | Alpha/Mushu direct |
| `stores/connections.py` | `e506356c2193e8d5735e6720bb6a376a25fd1d31` | Alpha/Mushu direct |
| `stores/mercadona.py` | `4a95f771c577d0edf5f9ded0888e622eb7144cac` | Alpha/Mushu direct |
| `stores/nappy.py` | `358b498d5895a558dc1cf0cd6598a93b5a239896` | Alpha/Mushu direct |
| `stores/public.py` | `3a713250de9e9eaf2c834ae0815160cbcbb2226c` | Alpha/Mushu direct |
| `stores/registry.py` | `6c53848a146ed0f2962f5e2f3d15fc9e51a6b939` | Alpha/Mushu direct |
| `telegram_io.py` | `ce8be26cc8f787fc1a3a9710d4ca459b88475982` | Alpha/Mushu direct |
| `tests/__init__.py` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` | Alpha/Mushu direct |
| `tests/agent_support.py` | `f093d5354267995c0ea7ab3aa3d55f72746e6435` | Alpha/Mushu direct |
| `tests/dialogue_support.py` | `7017002f81146dcf81865946264a4bd7ef55f4f3` | Alpha/Mushu direct |
| `tests/factories.py` | `4deb6ac249c5717a4e43ae88e0d7db6fc86a5510` | Alpha/Mushu direct |
| `tests/fakes.py` | `279e134afb286b9e18575503c965708cd360ad3e` | Alpha/Mushu direct |
| `tests/fixtures/stores/amascotados.html` | `458642afb2ae0110aad2e30a153b4e6b48a80309` | TAK-10 delegated |
| `tests/fixtures/stores/charro.html` | `35956ae96b08d287608d6276da63ac0a24a97d6d` | TAK-10 delegated |
| `tests/fixtures/stores/mercadona-search.html` | `3df5c77f3fd518b80d47ddb65790b927402c867f` | TAK-10 delegated |
| `tests/fixtures/stores/mercadona.html` | `932a71aa303f433e833f05eef8aef3c2fd32b43b` | TAK-10 delegated |
| `tests/fixtures/stores/nappy-out.html` | `ab41da49b583e3aee369bb647e33d934610e438f` | TAK-10 delegated |
| `tests/fixtures/stores/nappy.html` | `506f35ef89f23a189bbf5a77bec969620e3c410a` | TAK-10 delegated |
| `tests/guided_helpers.py` | `e6a246e9b26f75d486923d1c89e5deef00eac982` | Alpha/Mushu direct |
| `tests/stores/test_amascotados.py` | `cb3747698d7a4ca4c2b129c7ad469c5526f6e49e` | TAK-10 delegated |
| `tests/stores/test_browser.py` | `dec92ff021267d55317f34cfc30c6ba7b220e004` | TAK-10 delegated |
| `tests/stores/test_charro.py` | `6aeacb85104e6cd2b215361cba59a97bb582ced6` | TAK-10 delegated |
| `tests/stores/test_contract.py` | `042f3efad5e00b3761c87109ea26832205f90bd4` | TAK-10 delegated |
| `tests/stores/test_mercadona.py` | `21ccea18307022565d512b687a1469c827e10745` | TAK-10 delegated |
| `tests/stores/test_nappy.py` | `22b3e6bce2bb8a1e1ca111c730e30708836a2ad5` | TAK-10 delegated |
| `tests/stores/test_public_adapters.py` | `c9f91b28f1e636610a69e861f74e14e3e798f1ec` | TAK-10 delegated |
| `tests/test_agent_contracts.py` | `062c5c9c92442e8b42fe7e457dee3becb5b488b7` | Alpha/Mushu direct |
| `tests/test_agent_conversation.py` | `56ca390fd54eebd2f63a8ab8caf1e92e4c323be5` | Alpha/Mushu direct |
| `tests/test_agent_end_to_end.py` | `1cb9cd06435b41968ace74296db740018c306c81` | Alpha/Mushu direct |
| `tests/test_agent_ollama.py` | `26d85ac31567b3ab01664e81ebb1d1779512b0ae` | Alpha/Mushu direct |
| `tests/test_agent_probe.py` | `1247ba73bd8d96a2290f935100baeef5c001a855` | Alpha/Mushu direct |
| `tests/test_agent_proposals.py` | `b050d0cefae271b2383e73aed8c0ed4bcaca8ed1` | Alpha/Mushu direct |
| `tests/test_agent_recovery.py` | `23b0098f79a3c2c81e3feab4745976251d0acfa2` | Alpha/Mushu direct |
| `tests/test_agent_replies.py` | `ccf2c29b6ab6298ef71cfe932540b673db41843a` | Alpha/Mushu direct |
| `tests/test_agent_route_notices.py` | `b42ee649a6c8d01d0f358239101ffca48432d080` | Alpha/Mushu direct |
| `tests/test_agent_runtime.py` | `23c5ea7540f5049827efb5eefbc76840a1b3967e` | Alpha/Mushu direct |
| `tests/test_agent_skills.py` | `f2f89b90beab65c72edfca36c785df999db82066` | Alpha/Mushu direct |
| `tests/test_agent_storage.py` | `b262b88cc04e09ab41fc08549ae68e6d93b3485c` | Alpha/Mushu direct |
| `tests/test_agent_tools.py` | `f6217f994dd4757ddc4646de4181b1d41492e7c1` | Alpha/Mushu direct |
| `tests/test_checkout.py` | `49804573ea120822824f38ee0d5d3a720873560c` | Alpha/Mushu direct |
| `tests/test_command_query_provenance.py` | `e00fc2250041adffdda2a2d1c0f23756b31e4aa3` | Alpha/Mushu direct |
| `tests/test_conversation.py` | `1c6d52ab75c847ea8a8aa404fbb8baf4a6b4ad0a` | Alpha/Mushu direct |
| `tests/test_dialogue.py` | `bd9c6095becc6b92a23585128652b0c5df064bf3` | Alpha/Mushu direct |
| `tests/test_dialogue_conversation.py` | `28ce09dd20c287556512ba87e341b2ed325ccc9c` | Alpha/Mushu direct |
| `tests/test_dialogue_end_to_end.py` | `54322b1525eeb32b4c0f9a009bde735a8173c35b` | Alpha/Mushu direct |
| `tests/test_dialogue_increments.py` | `e07ce75a7972737cc6062312024f26017a59ed56` | Alpha/Mushu direct |
| `tests/test_dialogue_quantity_bounds.py` | `8edc2eba0aada0ccdb0aea1654fda49cb3c164bf` | Alpha/Mushu direct |
| `tests/test_dialogue_replacement.py` | `fef510d61b9642295e7346b9cd399dfd6c3021a1` | Alpha/Mushu direct |
| `tests/test_dialogue_requests.py` | `8fc406f0922cf881438a153d6d4dede3c9e8f2c4` | Alpha/Mushu direct |
| `tests/test_dialogue_storage.py` | `f8b7611a92047836dfaf8027d6d0cffa98366e41` | Alpha/Mushu direct |
| `tests/test_end_to_end.py` | `6ecc2887b880a189ed5ddb0afd38be83a40a5c9f` | Alpha/Mushu direct |
| `tests/test_guided_acceptance.py` | `148300c9f75bc3a485248d133d5c77134870d5a8` | Alpha/Mushu direct |
| `tests/test_guided_callback_cancel_reset.py` | `faec309090047ef08eda73b79857543e226b9a4c` | Alpha/Mushu direct |
| `tests/test_guided_contracts.py` | `ccd4bdf3385058ed85d5dcc657c4993f3d9c14e5` | Alpha/Mushu direct |
| `tests/test_guided_controller.py` | `b6ac8974aef965171366b70704ab92ad69df24bd` | Alpha/Mushu direct |
| `tests/test_guided_conversation.py` | `211f9aa538c33ecd48042fa9fc2803118e1393ee` | Alpha/Mushu direct |
| `tests/test_guided_events.py` | `fde816f7a52c0aa6fd90461ecb52357e41a7b738` | Alpha/Mushu direct |
| `tests/test_guided_final_fixes.py` | `623fbe3245c0f2145131466944f7357f0a5a3353` | Alpha/Mushu direct |
| `tests/test_guided_migration.py` | `30d6c4f0053f67724b588186f6a40fa025d4d579` | Alpha/Mushu direct |
| `tests/test_guided_native_integration.py` | `a3c587cc70fc6fb9950697cc2e372485f70028be` | Alpha/Mushu direct |
| `tests/test_guided_ollama.py` | `b347b54ff7dcc9e3e90604600e23306503842172` | Alpha/Mushu direct |
| `tests/test_guided_provenance.py` | `63542f614e82ea5a06193e568d779be8617907e3` | Alpha/Mushu direct |
| `tests/test_guided_replies.py` | `56e8f0b99b15967d4d7c441ab66ab3c41e56a9d8` | Alpha/Mushu direct |
| `tests/test_guided_runtime.py` | `d0a80abb808cf56b94fef823268ee0b3e9efb040` | Alpha/Mushu direct |
| `tests/test_guided_storage.py` | `6df0d8f8882d491df0ab238b73c22551facf26a4` | Alpha/Mushu direct |
| `tests/test_guided_telegram_io.py` | `59a7e0484d1d8d339a7ce0e223d7f6f498816679` | Alpha/Mushu direct |
| `tests/test_migration_distribution.py` | `d169cd94267719180ac0a19eea393c277605e2a2` | Alpha/Mushu direct |
| `tests/test_natural_dialogue_probe.py` | `8df7132be8b25468743e68a3bee89560a620b740` | Alpha/Mushu direct |
| `tests/test_natural_dialogue_runtime.py` | `8432b4697b86071f5a59105db7ac02ef87ae46ca` | Alpha/Mushu direct |
| `tests/test_natural_presentation.py` | `ac8bca1923ed5cd5910ae30fe74810272e5bdfd1` | Alpha/Mushu direct |
| `tests/test_offers.py` | `7493a4b83da26aaabcf02ea3d174aa840ab18883` | TAK-10 delegated |
| `tests/test_ollama_interpreter.py` | `9b79fec113291d1e7093ff0097065493e1df0d59` | Alpha/Mushu direct |
| `tests/test_ollama_replies.py` | `c6acf45a9fb581494c2cd648638670cd41c21d12` | Alpha/Mushu direct |
| `tests/test_pending_additions.py` | `78030f6aa926e066fc4d450db4013eca45c1c159` | Alpha/Mushu direct |
| `tests/test_presentation_replies.py` | `b1210bbfe2759869bc929716a4374f445fe63f1a` | Alpha/Mushu direct |
| `tests/test_presentation_storage.py` | `7a7df994736b3feff5e8f2de68fd8055063b87e3` | Alpha/Mushu direct |
| `tests/test_presentation_validation.py` | `0cb811b207f7cc0f4393b9e4f3f7b60c45015786` | Alpha/Mushu direct |
| `tests/test_private_acl.py` | `77a2601f8ab7c5f09feb8e67376d28118734a2d8` | Alpha/Mushu direct |
| `tests/test_product_memory.py` | `4fe7886b12f32afca88146a9dc45d1110420ab25` | TAK-10 delegated |
| `tests/test_product_queries.py` | `7a9442b036cb44a2a60342bd6a9ae73c29ff4da8` | Alpha/Mushu direct |
| `tests/test_recovery.py` | `e36138dc746110e5253ac8afac18250ad8badc4e` | Alpha/Mushu direct |
| `tests/test_reply_conversation.py` | `9c1b65468d663242358391310f45e1c45274f3ac` | Alpha/Mushu direct |
| `tests/test_reply_probe.py` | `eea017df7ac4c8a29c6c50936894cdf8a85e6c2c` | Alpha/Mushu direct |
| `tests/test_reply_runtime.py` | `8240a6e28251e12a54ba75e9cd5be58949f26d2b` | Alpha/Mushu direct |
| `tests/test_runtime.py` | `32a2fa7993156d85808254e6b57b14dd3e692ed3` | Alpha/Mushu direct |
| `tests/test_storage.py` | `e3fb04a57b4fbf53937f42f54159b2877436da38` | Alpha/Mushu direct |
| `tests/test_telegram_io.py` | `95e148daf0acc244345db4d7be70c018ccfc4c82` | Alpha/Mushu direct |
| `third_party/shopping-list-skill/LICENSE` | `fc495fc1af5e03149a3a38e8d048a75baa164a3f` | Alpha/Mushu direct |
| `third_party/shopping-list-skill/NOTICE.md` | `65ea214036244168f2f0cf06e37833a859b660ab` | Alpha/Mushu direct |
