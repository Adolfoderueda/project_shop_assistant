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
