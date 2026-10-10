# Task 7 — BLOCKED: real E4B acceptance fails

## Implemented

Added only the assigned acceptance/probe files and synthetic evidence. The probe
defaults to the installed E4B at the fixed local endpoint, with mandatory safe
output path and exit 0=PASS, 1=FAIL, 2=PENDING. Offline mode injects MockTransport
at HTTP only and explicitly reports real quality NOT_TESTED. Every natural
real step runs real AgentConversation, OllamaShoppingAgent, native tools and
temporary Repository; the legacy interpreter raises if asked to parse naturally.

Independent oracles and native ledger cover interpretation, executed action,
arguments, rows/proposal/review permission, reply facts, safety, complete context
and 24,000-byte messages-plus-tools budget. Frozen hashes cover skills, schemas,
system prompt, matrix source, prompts/oracles and installed model metadata.
The controller snapshot remains complete, including overflow tests.

Matrix includes weekly arroz+carne pending quantities, saved-list queries during
drafts, explicit multiple products, negatives/conditions, brands/size/grams,
candidate selection, known/unknown increments, cancellation, replacement,
internal/existing duplicates, draft edits, 15-minute expiry, changed/reserved/
deleted rows, full-batch atomic conflicts, restart/unsent outbox/replay, hostile
data/tools/authority, and old v1/v2 jobs/commands. No private Settings/DB,
Telegram/browser/checkout, activation/downloads or process changes.

## TDD and verification

Detailed commands/output: `docs/superpowers/evidence/2026-10-08-skills-agent/verification.txt`.

- RED: named initial tests, 22 failures because the new probe was absent.
- GREEN: initial 22/22, expanded 28/28; no legacy test expectations removed.
- Additional RED: 2 reply-oracle tests exposed acceptance of false success and
  invented facts; added independent factual and confirmation-permission checks.
- Final focused: **30 passed in 40.57s**, targeted Ruff clean.
- Full suite once after final code: **1195 passed in 351.49s**, no warnings.
- `git diff --check`: pass.
- Global Ruff: **FAIL, seven baseline diagnostics** in unchanged tools.py,
  test_agent_conversation.py and test_agent_runtime.py. See verification; their
  git diff is empty. No unrelated legacy/security changes made to force green.

## Real outcomes — acceptance NOT complete

Final offline: **76/76 simulated steps PASS**, NOT real quality.
Two final frozen real passes completed in foreground: each **31/53 real steps
pass, 22 fail**; each also contains **23/23 separately labelled simulated boundary
steps**. Exact same input hashes and failures. All real safety/context/budget
checks pass; this does NOT override semantic/action/quantity failures.

All-case table, failure explanations, hashes, raw model/tool outputs, states,
reply facts, and latency distributions are retained in the evidence README and
JSONL artifacts. Both full real runs exit 1. Do not activate/deploy.

The initial pre-freeze diagnostic is also retained honestly. Self-review found
three overly literal expectations: description omitted a harmless “de”, safe
conditional clarification's subsequent yes legitimately reported no draft, and
an unknown-base selected row legitimately used its saved full description.
Corrected these before final freeze, without accepting wrong tools, omitted
quantities or review permissions. Later reply-oracle tightening increased failed
dimensions, not successful real steps. Frozen final scripts were unchanged
between the two retained final real passes.

Observed cold-like initial request: **30,260.942 ms**, native load duration
**29.191 s**; no forced unload/restart. Final warm-like passes: first requests
457.695/346.729 ms, subsequent medians 355.706/354.039 ms, maxima
1,100.752/1,095.766 ms. No performance promise or global success percentage.
Max context real 11,230 bytes; offline 11,926 bytes, based on actual ledger payloads.

## Systematic diagnosis / smallest production follow-up

Reproduced nested `item_name` instead of required `description` repeatedly for
multi-product captures. Strict validator rejects before execution. Inspected
schema exposure: nested `$defs/$ref` models. An isolated real end-to-end A/B
changes only exposed schemas by inlining identical local definitions, with
unchanged strict contracts, prompts, skills, parameters, real tools and repo.
Recorded in `schema-diagnostic.jsonl`, explicitly NOT frozen acceptance.

Reference-schema weekly arm: capture fails with item_name, query passes,
completion fails, confirm fails. Inlined arm: initial capture passes, query
passes, completion still FAILS (wrong proponer_altas rather than completar_propuesta),
confirm passes. Thus schema inlining fixes that observed capture issue but is
not sufficient for acceptance. Other independent failures: saved-list query
uses proposal tool, increment/replacement omit explicit quantities, natural
duplicate decisions return prose only, draft edits lose selection/use saved-row
changes. Safe fallback does not make these successes.

Smallest needed production correction: inline local definitions at existing
`shopping_agent.tools.tool_definitions`, preserving strict validators/authority.
Then address existing skills/runner draft-tool selection and quantity retention
with TDD and repeat the entire real matrix twice. No item_name compatibility
alias, preselected Intent, phrase catalog, framework or alternative protocol.
No production files changed here: acceptance remains blocked for controller
review/follow-up rather than deploying a partial diagnostic fix.

## Files changed

- `scripts/probe_skills_agent.py`
- `tests/test_agent_end_to_end.py`
- `tests/test_agent_probe.py`
- This report
- Evidence directory: README.md, verification.txt, offline.jsonl,
  real-pass-1.jsonl (initial), frozen-real-pass-1.jsonl,
  frozen-real-pass-2.jsonl, schema-diagnostic.jsonl.

## Self-review, limits, concerns

- Probe is a single focused standalone matrix/ledger/oracle file as assigned;
  relatively large because literal scenario expectations remain auditable.
- Schema diagnostic modified only a function binding in an isolated diagnostic
  process; source modules and running bot/model configuration remain untouched.
- Real TTL/restart scenarios FAIL because initial drafts are not established;
  offline safety cannot be claimed as successful real flows.
- Real send failure/Telegram acceptance was not attempted. Unsent durable notices
  model failed delivery; existing full-suite tests additionally cover outbox
  rollback and post-commit lost results. Historical commands remain verified
  by legacy tests; no legacy security expectations changed.
- Sentinel guards reject private file/SQLite access; synthetic temp DB only.
- Default source model is E4B; no Settings loaded by the probe.
- Wheel distribution check DEFERRED; no setuptools/install authorization.
- Global Ruff baseline errors and real semantic quality are blockers.
- Independent controller review still required; no subagents spawned, no
  merge/push/activation. Commit is evidence/tests, NOT acceptance approval.

---

## Fix round 1 — schema/harness fixes verified, acceptance still FAIL

Full fix report and all-case tables:
`docs/superpowers/evidence/2026-10-08-skills-agent/fix-round-1.md`.
This section supersedes the original lint blocker and production-follow-up status;
all original failed traces/frozen artifacts remain unchanged.

### Changes implemented

- Inlined identical local `$defs/$ref` schemas in existing tool_definitions.
  Runtime contracts/validation/permissions unchanged; item_name still rejected.
- Proposal reply oracle now independently verifies displayed known/pending
  quantities, requested additional amounts and arithmetic, not only names/prompt.
- Ledger captures raw malformed response text and decode failure, returning the
  unchanged HTTP response to the real runner so invalid_model/evidence survive.
- Retained two separately tested skill improvements: active-draft patch recipe
  in propuestas and requested-quantity slot in cambios. Four fixed skills remain
  204/307/106/366 words; no phrase catalog or confirmation authority.
- Actual production-source file hashes added to metadata.
- Self-review expiry regression: permission oracle now compares parsed instants,
  not lexical Z/+00:00 spellings, and denies the exact TTL boundary.
- Reproducible synthetic-setup/fresh-real-context diagnostic script/evidence.
- Mechanically fixed the seven earlier-task branch Ruff diagnostics (six fixes)
  in tools.py, test_agent_conversation.py and test_agent_runtime.py. These were
  this branch's responsibility, not an indefinitely acceptable baseline blocker.

### TDD RED/GREEN and commands

Regressions first: proposal-reply quantity None/2 and arithmetic mutations,
malformed HTTP body retention, schema-equivalence/no-reference and strict
item_name rejection. Command selecting these tests in test_agent_probe/tools:
five expected RED failures and one existing strict-validator PASS. Corrected one
test's schema dialect assumption (exclusiveMinimum 0, not minimum 1); constraints
remain exactly equivalent. GREEN probe/end-to-end 34 passed (39.35s), tools/Ollama
65 passed (4.11s). Original isolated actual E4B shape failure remains RED evidence.

Final focused covering probe/end_to_end/tools/ollama/skills/conversation/runtime:
**123 passed in 78.79s**, exit 0. Full suite after final expiry correction:
**1202 passed in 361.11s**, exit 0. Global Ruff **PASS**, exit 0; diff checks PASS.
Earlier pre-self-review verification was 122 focused / 1201 full-suite passing;
the expiry regression then showed one RED failure (15 deselected), was fixed,
and both focused/full and the frozen real artifacts were freshly rerun. The
second full-suite run was necessary after that final correctness change, not
an iteration loop of full-suite runs during skill wording experiments.
Exact commands/output are recorded in fix-round-1.md; no other suite run is
silently omitted. No wheel/distribution build or installation attempted.

### Evidence-backed real progression / bounded hypotheses

Schema-only change with original skills: 13 real failed steps (previously 22),
retained `fix1-schema-only-real.jsonl`. No prompt/schema bundle in that experiment.

H1 conditional active-draft recipe: six micro cases had 0/5 each before edit;
four improved to 5/5, two remained 0/5. H2 explicit quantity slot: ambiguous
increment/replacement/unknown-base each improved from 0/5 to 5/5. Both retained.
Each sample is a fresh real E4B conversation after explicitly labelled simulated
tool/repository setup, not a natural parser; full original real matrix remains
the acceptance gate.

H3 duplicate JSON slot example initially looked improved in simplified micro
fixtures, but failed the full original-context trace. Corrected fixtures to
match actual original messages, units, rows and intervening yes, and ran five
fresh samples with/without example: both 0/5 internal duplicate. Reverted the
unproven example. H4 query-scope recipe (separate variable after clear H1/H2
improvement) stayed 0/5 and introduced a wrong duplicate capture/early changed-row
commit in its full matrix; its safety failure is retained honestly. Entire H4
addition reverted. No fifth hypothesis or further prompt tweaking; no catalogue,
framework, alias, second parser, model download/context expansion or authority.

### Final frozen acceptance (completed foreground, no pending verification)

`fix1-final-offline.jsonl`: **76/76 PASS**, real quality NOT_TESTED.
`fix1-final-real-1.jsonl` and `fix1-final-real-2.jsonl`: **each FAIL / exit 1**,
50/53 real steps pass, three fail; 23/23 separately labelled simulated boundary
steps pass. Equal skills/schemas/prompts/oracles/script and actual production
hashes confirmed; model/parameters unchanged. Every final real safety, budget
and complete snapshot/context check passes, but does not override semantic FAIL.

Remaining exact failures in both frozen runs:
1. explicit update 2: saved-list inquiry incorrectly calls consultar_propuesta,
   showing draft items while saved rows are empty (action/interpretation/reply FAIL).
2. internal_duplicate update 3: completar patches repeat quantity/unit but omit
   duplicate_decision separate for both positions; controller leaves review unset.
3. internal_duplicate update 4: ensuing yes correctly cannot commit, so required
   completed-flow state/reply FAIL. Neither tested duplicate example nor scope
   recipe fixed their exact contexts reliably; stop instead of loosening oracle.

Final observed real max context 14,106 bytes of messages+tools; full controller
snapshots/candidates retained. First final request 28,945.447 ms, native load
27.685 s (cold-like); second pass first 353.038 ms (warm-like). Subsequent medians
337.496/346.758 ms, maxima 898.307/892.457 ms. No timing or
global quality percentage promised; original cold-like observations retained.

### Exact changed source/test files and review concerns

Production: shopping_agent/tools.py (schema exposure + import order),
shopping_agent/skills/propuestas.md, shopping_agent/skills/cambios.md.
Harness: scripts/probe_skills_agent.py.
Tests: tests/test_agent_probe.py, tests/test_agent_tools.py;
tests/test_agent_conversation.py and tests/test_agent_runtime.py mechanical lint
only (import order/spacing, unused import, redundant return; no expectations lost).
Reports: this appended report, evidence README/fix-round-1.md, new fix1 JSONLs
and skill_micro_probe.py. consultar/altas skills have no retained change.

Schema expansion assumes current fixed contracts are acyclic/local, deliberately
not a generic schema framework. Diagnostic micro fixtures are not equivalent to
real full flows; the corrected exact-context H3 result demonstrates this limit.
Rejected H4 wrong-tool/write outcome is visible, not advertised as safe. Final
configuration improved markedly but real semantic acceptance remains BLOCKED.
No deploy/activation/private data/external effects/subagents; controller review
and a bounded decision on remaining two interpretation limits are required.
