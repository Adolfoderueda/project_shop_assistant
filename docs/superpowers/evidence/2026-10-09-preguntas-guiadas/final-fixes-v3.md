# Final guided fixes and version3 evaluation

Activation remains **BLOCKED**. Unit tests or a few improved model outputs do not
replace full native dialogue acceptance. No private settings, DB, Telegram, model,
resource limits, activation, restart, installation, merge or push changes.

## Application changes and deliberate UX limit

- Validated rejected callbacks and undelivered-copy reoffers do not poison prompt
  history; last three eligible completed owner pairs are selected. Existing consumed
  provenance is validated first; corrupted successful choices still fail closed.
- Expired guided/question/topic/legacy recipients require independent application
  reset. Exact `Cancelar` discards pending state atomically, not saved rows. A real
  fresh slash command remains deterministic. Audit events remain; inference history
  stops at the real durable reset/fresh-command boundary. No inferred natural request
  silently resets expired state; no phrase catalogue or literal-citation authority.
- The user now needs an extra reset turn. Original `expired-guided` and
  `legacy-expired` same-turn convenience expectations remain unchanged and may fail.
  Those failures are not exempted from acceptance.
  This conservative boundary was ruled by the controller under the user-approved
  plan, not directly approved by the user as a specific UX change; it must be disclosed.
- Full oversized nonreview questions/candidates/topics remain durable, but no choice
  tokens/keyboard are offered. A deliverable reduce/divide notice is sent; no facts
  are truncated, no artificial scope or pagination framework is added.
- Reduction uses a refreshed post-inference clock and the expected question version.
- The independent stdlib verifier rejects wrong role, error/refusal envelopes,
  nonstring content and nonobject envelope/message, even with forged candidate labels
  and updated raw base64. Current manifests still pin exact current runtime bytes;
  immutable v2 executions use their exact archived source reconstruction, not a hash waiver.
- SQL migrations001–010 are unchanged and explicitly declared package resources.
  Source/importlib-resource tests are not installed-wheel verification. Existing build,
  wheel and setuptools modules are absent; actual installed-distribution testing is blocked.

## Native diagnosis: tested hypotheses, not a promise

Version1 frozen2026-10-09T17:34:08+02:00, original source byte SHA256
`c2ae62609a9f1e8a34f28665dd189158c187f05c74c9f8f49bcae2816a876075`
retained verbatim in `native-diagnosis-v1-source.txt`. Nine calls, three synthetic
inputs, three preregistered arms. Raw artifact SHA256
`deaa9894e4014181d55f839576b0142d984d5d5f4c1f0c2c59b2d11786f4ba7f`.

| Arm | Native tool responses / inputs |
|---|---:|
| Guided baseline | 0/3 |
| Guided + descriptions only | 0/3 |
| Actual original agent request | 2/3 |

The shared add/change/list parameter schemas are identical. The original uses
function descriptions, additional tools, its existing skills and a differently
shaped context; that comparator changes multiple factors and is not causal evidence
alone. Descriptions-only falsified the first hypothesis. Tool-like content such as
`proponer_altas(items:...)` in `message.content` is not a native tool call. The two
original native responses establish actual model/server native tool support.

Version2 frozen2026-10-09T17:37:46+02:00, script SHA256
`5111d19cf22468d78eeffba8098eb051d53e4d876bf77d096fb3c72c40315935`.
Six calls: baseline versus appending existing unchanged `load_skills()` only. Raw
artifact SHA256 `0d10be55fed72febd537ff34169fd0706f8a66c81d18834b73d4e89b5724b82d`.
Baseline0/3; existing-skills2/3 native. Both native skill-arm outputs correctly keep
all requested items and unknown quantities on those two inputs. `leche dos` still
has no native tool. This supports narrowly reusing the existing skill integration;
it does not establish reliable quality across other cases. No new prompt recipes,
phrase hacks, prose decoder, schema relaxation or resources were added. Larger
unchanged skills consume more of the same24000-byte context budget, with overflow
still a controlled failure.

All diagnostic requests/responses include exact base64 and SHA256. Their source,
raw-byte equality, fixed model/options and context budgets were checked independently
with stdlib. Requests use only existing localhost `/api/tags` and `/api/chat`.

## Frozen new evaluation

`matrix-v3.json` contains all26 original cases byte-value unchanged plus two additive
explicit-reset security scenarios. Three repetitions,28cases/55paths/165conversations,
732planned steps. Original denominators remain separately observable: bounded102,
security27, general-free24. Added reset scenarios contribute12security conversations.

Freeze2026-10-09T15:48:34.082801UTC (`acceptance-v3-freeze.json`):
- Original matrix SHA256 `f21df63882f2269e7bd38cfa25eed21f4822e21b67f686d5f5deb224cff6c53e`.
- New matrix SHA256 `14c70781ef6caa9aa3a0995d41319d4fd0332aa47085cee02cbf6eeebaabf94c`.
- Verifier/probe v4 SHA256 `e8026771b4af2f9d55f39ef830057be29509aa705c42c7df3fb972eb9e8d5902`.
- All runtime/migration/skill hashes and fixed parameters are in the freeze and run
  manifests. Neither old frozen matrix nor old raw artifact was edited.

Full offline/real executions and final full pytest suite were launched on this
frozen code. Actual outcomes will be appended only after completion and independent
verification; no acceptance success is claimed from an in-progress run.

### Completed offline v3 and independent verification

Both execution and separate `--verify` exit1, identical36errors, no integrity mismatch:
- bounded102/102; security30/39; general-free24/24.
- Original-only security18/27. Both original expiry convenience cases fail exactly
  at the forbidden same-turn natural restart: expired-guided6conversations and
  legacy-expired3. These9failures are not waived.
- Added explicit-reset scenarios12/12 complete with expected state. Expired input
  and actual Cancelar use zero inference; the subsequent new-request history is empty.
-723executed/9unexecuted steps of732;354fixture model turns:348candidate/6invalid;
 150simulated button steps. Invalid6/354 is a conservative fallback denominator,
 not evidence of understanding. Offline is a fixture/integration measurement only.
-0tagged security invariant failures in executed evidence is NOT full acceptance;
  failed workflows and unexecuted steps remain blockers.
- `offline-v3.jsonl`:733records/18137888bytes, SHA256
  `be8716967aeb709c2c716522ab80dda9be39ad6dc072e9345c8431bfeafe8637`.

Exact commands (existing venv `-P`, worktree PYTHONPATH):
```powershell
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json --mode offline --output docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v3.jsonl --repetitions 3
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json --verify docs/superpowers/evidence/2026-10-09-preguntas-guiadas/offline-v3.jsonl
```

### Completed real v3 and independent verification — still BLOCKED

Execution and separate stdlib `--verify` both exit1, identical673errors and exact
current source hashes. No source/prompt/matrix change after freeze or rerun to hide
failures. Fixed existing E4B/model/options/native-only/resources, three repetitions.

| Measurement | Real v3 |
|---|---:|
| Bounded conversations |41/102|
| Security conversations, original + additions |6/39|
| Original-only security conversations |6/27|
| Added explicit-reset conversations |0/12|
| General-free conversations |0/24|
| Executed / unexecuted steps |348/384 of732|
| Model turns |228|
| Validated candidates (not necessarily correct interpretation) |119/228|
| No-native clarify fallback |90/228|
| Invalid-native fallback |18/228|
| HTTP failure fallback |1/228|
| Simulated button steps |43|
| Final witnessed saved-write steps |47|

Total fallback109/228 is NOT comprehension. Tool-like prose/JSON content remains
ignored. Zero verifier-tagged invariant violations in the executed subset does NOT
demonstrate all security criteria:33/39 security workflows fail and384steps were never
reached. All failed/unexecuted inputs remain in the raw artifact; no activation.

Original v2 bounded6/102 improved to41/102 on the unchanged original bounded cases,
but still misses the required102/102. This validates limited integration improvement,
not acceptance, and temperature-zero repetitions are not independent statistics.
Replacement now completes6/6; original saved-query/internal-duplicate acceptance
remains open and fails0/6 on each. No more prompt iterations were attempted.

#### Complete per-case residual inventory

All totals below include both paths ×3repetitions except legacy-expired (3).

| Case(s) | Completed/total | First failing step / concrete residual |
|---|---:|---|
| one-each |5/6|Step1 HTTP500 on button/repetition1; other5complete|
| shared; partial-reordered; different-partial; condition-unit; increment; replacement |6/6 each|Complete with expected state|
| query-then-answer; topic-no-then-append; cancel; query-plus-answer; second-topic |0/6 each|Step1 single-product request emits tool-like content, no native tool|
| internal-duplicates |0/6|Step1 content `pedir_aclaracion`, no native duplicate proposal|
| correction-mixed-final |0/6|Step2 plain JSON patches in content, no native correction; old review remains|
| ambiguous-selection |0/6|Step2 tool-like proponer_altas content, no native assignment candidate|
| unknown-base |0/6|Step3 native proponer_cambio/set_quantity5 instead of focused responder_cantidad; inert change candidate preserves unknown quantity|
| saved-query-duplicate |0/6|Step1 wrong set-total operation with unsupported unit `unidades`; strict validation rejects|
| delivery-unknown; expired-guided |0/6 each|Step1 tool-like proponer_altas content; later delivery/expiry steps not reached|
| legacy-expired |0/3|Step2 safely uses no inference; step3 forbidden same-turn natural restart remains blocked by controller ruling|
| reservation |6/6|Complete with expected current unreserved source and quantity|
| unknown-unit |0/6|Step1 tool-like content, no native initial proposal; later unsupported-unit test not reached|
| Los-3-es-uno |0/6|Step2 collective tool-like proponer_altas content, no native candidate|
| Uno-de-cada-uno |0/6|Step2 unoffered responder_cantidad with positions (no selected focus), rejected|
| reordered-answer |0/6|Step2 unoffered legacy completar_propuesta, rejected; unchanged skills do not reliably obey guided-tool branch|
| dos-carne-resto |0/6|Step2 multiple tool-like cambio strings in content, no native candidate|
| explicit-reset-guided |0/6|Step1 no native tool; reset scenario not reached|
| explicit-reset-legacy |0/6|Actual expiry/reset have no inference; new milk request at step4 emits only content pedir_aclaracion. Fresh inference history is empty, but quality fails|

HTTP227responses200; one initial500 returned:
`llama-server process has terminated: exit status 0xc0000409 ... CUDA error: shared object initialization failed`
with context initialization details retained exactly in raw bytes. This is concrete
backend evidence, not a timeout guess. No server restart, resource increase or retry
experiment was performed. Failure remained an inert controlled model_failure.

`real-v3.jsonl`:733records/9880770bytes SHA256
`261b84b63ebfc2fc21f325625dd6a485f92f941e65d5cc09edb9dc23acb9c254`.

```powershell
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json --mode real --output docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v3.jsonl --repetitions 3
& '../../.venv/Scripts/python.exe' -P scripts/probe_guided_questions.py --matrix docs/superpowers/evidence/2026-10-09-preguntas-guiadas/matrix-v3.json --verify docs/superpowers/evidence/2026-10-09-preguntas-guiadas/real-v3.jsonl
```

Original full-suite notification: `-m pytest -q`, timeout1800000,
**1631passed in839.00s(0:13:58)**, exit0, no failures/warnings. Ruff/diff checks clean.
No source/test edits occurred between this freeze and that run's completion.

Final self-review then reproduced an additional history/reset regression: a valid
cached pre-reset callback replay occurring after Cancelar can contribute its old
summary to the next inference segment. Three such replays also hide the reset from
the old last-three-pair scan. Two new tests RED (`-k valid_successful_callback_replays`):
2failed27deselected0.78s. No inference or saved mutation is required to reproduce it.
This is a concrete finding1/2 lifetime issue, not a prompt-quality speculation.
V3 is preserved as a verified but BLOCKED checkpoint, not final fixed-source
acceptance. The same wave will narrowly repair the segment boundary and register
v3's exact source cohort for archival verification before a new coherent freeze.
No prompt iteration or duplicate of a still-live run is authorized or performed.
