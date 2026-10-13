# Final wave — corrected UTF-8 evaluation5

Acceptance/activation remains **BLOCKED** pending complete evidence and unmet gates.
Final suite/execution/independent verification are now complete; unmet gates below
still block acceptance. Earlier pending statements are chronological history.

## Final scoped re-review: HIGH callback cancellation boundary residual

Controller-supplied sole final scoped re-review identifies a remaining safety gap
in `_guided_history_boundary`, guided_storage.py427–443: it scans only inbox messages.
Authenticated review `Cancelar` callback clears pending proposal but creates no
inference-segment boundary. Reproduction reported by that review: apply `one_each`,
then cancel the review with its authenticated callback; replay the earlier successful
callback three times; history again contains old `Uno de cada` pairs. A subsequent
bare `2` plus injected stale native output creates a fresh `huevos: 2` review.
No saved mutation is claimed here; stale inference recipients are nonetheless unsafe.

The local RED/GREEN tests cover text Cancelar, not this callback-cancellation path.
V5 omits this case. Frozen scores remain their actual measured values, but zero
executed-subset invariant violations is NOT total safety and cannot waive the gap.
This residual was supplied by the final review; no new reproduction run, source/test
edit, matrix change, prompt iteration or suite/probe was performed afterward.

Controller ruling: candidate unsafe to activate, flag off/unmerged; explicit follow-up
required. Single final fix/re-review cap reached; do not repair silently in this wave.
Review disposition:findings1/4/5/6/7 addressed;2partial (this HIGH residual),3real-native
criteria unmet,8packaging partial (actual wheel unverified). Controller owns ledger
and conservative expiry-reset ruling; extra reset UX turn remains disclosed separately.
This is the same final fix wave. [V3](final-fixes-v3.md) records original fixes,
native diagnosis, full1631-test suite, offline/real outcomes. [V4](final-fixes-v4.md)
records RED/GREEN lifetime regressions, narrow source repairs, archive registration,
and explicitly invalid matrix generation. No original archived data was modified.

## Corrected experiment definition

V4 default-decoded UTF-8 on Windows, corrupting accented inputs. It cannot count
as unchanged-case acceptance. Its raw/freeze/matrix bytes are preserved. Both v4
probes finished before v5 probes launched; the final full suite already running
covers exactly the same application/verifier/test bytes and was not duplicated.

Matrix5 generation and independent readbacks explicitly use UTF-8: all28cases equal
v3, first26equal original v2. No expectations relaxed.28cases/55paths/
165conversations/732steps,3repetitions. Existing E4B/native-only/options/budgets unchanged.

Freeze5:2026-10-09T16:38:18.858501UTC, `acceptance-v5-freeze.json`:
- Matrix SHA256 `affb3024d6f51f05a866f03a484974e1ff12f7208b35b9e14c4a754246d7b6ae`.
- Probe/verifier5 SHA256 `7947418626b1f932f815aaddce44799737bddcd4bcef86755a8549f06e9bd76b`.
- Application/verifier/test hashes unchanged from freeze4. Only matrix generation
  corrected; no prompt iteration or source changes after freeze4.
- Focused repair verification263passed93.44s; whole Ruff/diff clean.

```powershell
$env:PYTHONPATH=(Get-Location).Path
& '../../.venv/Scripts/python.exe' -P -m pytest -q
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v5.json --mode offline --output docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v5.jsonl --repetitions 3
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v5.json --mode real --output docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v5.jsonl --repetitions 3
```

Timeouts1800000/1800000/3600000 respectively; inference120s unchanged. Actual final
results/independent verification await completion notifications. No polling.

Final full-suite notification received: **1641passed886.58s(0:14:46)**, exit0.
Exact `-P -m pytest -q` against unchanged freeze4/freeze5 source and tests; no
duplicate suite. No failures/warnings;263focused repair tests also pass.

## Independent remaining gates

1. Application/verifier/resource fixes require final full-suite result; targeted263
   pass. Post-reset provenance remains fail-closed/idempotent; saved rows/audit preserved.
2. Native comprehension differs from fallback safety. Last valid v3 real:41/102
   bounded,6/39security,0/24general; not final repaired-source acceptance. Original
   Task7 saved-query/internal-duplicate native acceptance stays open.
3. Expiry reset is the CONTROLLER ruling under approved plan, not direct user approval
   of the extra UX turn. Original convenience expectations stay failed, not exempted.
4. Actual installed-wheel verification blocked: build/wheel/setuptools absent,
   installs forbidden. Source resources/manifest tests are not wheel verification.

## Initial vs intermediate valid real evidence (v5 pending)

| Measure | Initial v2 original26 | Improved v3 original26 | v3 all28 |
|---|---:|---:|---:|
| Bounded |6/102|41/102|41/102|
| Security |6/27|6/27|6/39|
| General |0/24|0/24|0/24|
| Executed / unexecuted |186/486|318/354|348/384|
| Model turns |159|216|228|
| Validated candidates |33|119|119|
| Fallbacks |126|97|109|
| Clarify / invalid / HTTP failure |114/12/0|78/18/1|90/18/1|
| Simulated button selections |12|43|43|

Controls differ from comprehension: v2 executed27non-model steps, all27validation
passes; v3 all28 executed120non-model steps,117passes (3original legacy-expired
convenience failures). V2 slash controls3executed/15planned; v3slash9/21. Button-path
totals contain model turns and are not counts of deterministic button selections.
More reachable candidate states permit more controls; no control/fallback is counted
as model comprehension. Original vs added denominators are separated explicitly.

## Completed offline5 independent verification

Execution and separate `--matrix matrix-v5.json --verify offline-v5.jsonl` both exit1,
identical36errors. Current-source integrity matches.102/102bounded,30/39security,
24/24general;723executed9unexecuted/732,354fixture model turns348candidate6invalid,
150simulatedbuttons. Original security18/27; added explicit-reset scenarios12/12.
Nine original same-turn expiry convenience workflows remain failed, not waived.
This is fixture/application evidence, never real-native comprehension.
Raw733records18137969bytes SHA256
`ce9e9333062b2f046b97a74653ff0865a6e610356bdde45c456db6c78f66d92a`.

## Final real5 — independently verified, acceptance BLOCKED

Execution and separate `--matrix matrix-v5.json --verify real-v5.jsonl` exit1,
identical666errors. Recorded/current verifier and runtime hashes match freeze5.
All228HTTP responses200; no HTTP fallback. Raw733records9909971bytes SHA256
`57ed044a54bf53c28ff55af7467d33e16191dab81679f64aa0b18270eff2e938`.

| Measure | Initial v2 original26 | Final v5 original26 | Final v5 all28 |
|---|---:|---:|---:|
| Bounded |6/102|42/102|42/102|
| Security |6/27|6/27|6/39|
| General |0/24|0/24|0/24|
| Executed / unexecuted |186/486|321/351|351/381|
| Model turns |159|216|228|
| Validated candidates, not necessarily correct |33|126|126|
| Clarify / invalid / HTTP fallback |114/12/0|84/6/0|96/6/0|
| Total fallback / turns |126/159|90/216|102/228|
| Simulated deterministic button selections |12|45|45|
| Executed non-model controls / validation passes |27/27|105/102|123/120|
| Slash controls executed / planned |3/15|3/15|9/21|

Added reset real0/12; original security6/27. Extra controls/buttons reflect more
reachable proposal states, NOT extra understanding. Native candidates are inert
and may be semantically wrong; fallback is never comprehension. Zero executed-subset
invariant violations cannot establish security acceptance with381unexecuted steps.
Temperature-zero repeated results are not independent statistical samples.

### Complete final case inventory

Completed6/6each: one-each,shared,partial-reordered,different-partial,condition-unit,
increment,replacement,reservation. Replacement preserves quantity2 in all6real paths.
Every other case fails0/6, except legacy-expired0/3:
- Step1 no-native prose: query-then-answer,topic-no-then-append,cancel,
  delivery-unknown,expired-guided,query-plus-answer,unknown-unit,second-topic,
  explicit-reset-guided. Later safety/expiry steps in those workflows are unreached.
- internal-duplicates step1 content `pedir_aclaracion`; saved-query-duplicate step1
  JSON set_quantity in content, not native. Original Task7 acceptance stays open.
- correction-mixed-final step2 JSON patches in content; ambiguous-selection step2
  tool-like proponer_altas in content. No prose parser added.
- unknown-base step3 native proponer_cambio/set_quantity5 instead of focused quantity
  answer; unknown quantity remains unchanged, workflow quality fails.
- Los-3-es-uno step2 tool-like add content; dos-carne-resto step2 multiple prose
  change strings. Uno-de-cada-uno step2 validated native add of threeitems1 each,
  but topic observed where scope expected: a native call is not enough.
- reordered-answer step2 unoffered legacy completar_propuesta, invalid/rejected.
- legacy-expired step3 required reset notice/no inference, old same-turn restart
  expectation fails. Original expiry convenience expectations are unchanged.
- explicit-reset-legacy expiry/Cancelar perform no inference; step4 fresh milk request
  uses empty old history in all6paths, but emits only content pedir_aclaracion.
  Added guided-reset real never reaches reset; offline12/12 is not real12/12.

### Final gate separation

Concrete application/verifier/source-resource repairs: RED/GREEN263focused tests,
final full1641passed886.58s, Ruff/diff clean, immutable v2/v3 independently verified.
Native quality improved bounded6/102→42/102, but mandatory full criteria fail;
security6/39 and general0/24 remain blocked. Controller's conservative reset ruling
adds a UX turn and deliberately still fails original convenience expectations; this
must be disclosed, not attributed as direct user approval or waived. Packaging source
checks pass, but actual installed-wheel verification remains unperformed/blocked.
No activation/restart/install/private DB/settings/Telegram, agents, ledger edits,
model/resource changes, prompt iteration, merge or push.
