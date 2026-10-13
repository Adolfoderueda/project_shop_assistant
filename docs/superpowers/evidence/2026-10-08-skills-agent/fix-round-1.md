# Task 7 fix round 1 — acceptance FAIL, bounded investigation complete

Original failed traces/initial frozen artifacts are unchanged. Current final
artifacts: `fix1-final-offline.jsonl`, `fix1-final-real-1.jsonl`,
`fix1-final-real-2.jsonl`. No deployment/activation or external effects.

## Changes and TDD

1. `shopping_agent/tools.py` now exposes the **identical** fixed, acyclic local
   schemas with `$defs/$ref` inlined. No runtime contract, field alias, dispatcher,
   authority, parser, endpoint or model change. Recursive schema-equivalence and
   no-reference tests prove constraints/required fields are preserved. The real
   validator still rejects `item_name` and every earlier malformed/forged input.
2. Proposal-reply oracle independently checks each numbered item's displayed
   quantity (including pending quantity), requested additional amount, and
   applicable base + additional = total arithmetic, using controller facts rather
   than the renderer. Regressions change ONLY reply quantities/arithmetic while
   keeping state correct; those replies now FAIL.
3. Ledger records raw response text, attempts JSON decoding defensively and returns
   the unchanged response. Malformed bodies reach the real runner, produce
   `invalid_model`, retain the step/ledger evidence and cannot PASS semantic quality.
4. Mechanical lint only in tools.py, test_agent_conversation.py and
   test_agent_runtime.py: import order/spacing, unused Reply import, redundant
   `return None`. Seven prior diagnostics (six fixes because return diagnostics
   overlap) resolved. No security expectation removed.
5. Retained only evidence-backed additions to existing propuestas/cambios skills:
   conditional active-draft patch procedure/JSON example and explicit requested
   quantity slot independent of unresolved selection/base. Four resources remain
   short: altas 204, cambios 307, consultar 106, propuestas 366 words.
   Conditions/reviews/confirmation remain application-owned; MIT notices preserved.
6. Probe metadata now includes hashes of the actual production modules in addition
   to skills, native schemas, prompts/oracles, matrix script and installed model.
7. Self-review found a permission-oracle equality bug: ISO spellings `Z` and
   `+00:00` were compared lexically. Added a RED regression changing only the
   observation clock to exact expiry (one failure, 15 deselected), then compare
   parsed UTC instants. Application control was already safe; the independent
   oracle is now strict at the exact 15-minute boundary too.

RED command:
```text
python -m pytest tests/test_agent_probe.py tests/test_agent_tools.py -q -k "proposal_reply_oracle or malformed_body_transport or native_schemas or nested_item_name"
```
Five expected failures: wrong displayed pending/known amounts and arithmetic passed,
malformed body aborted in LedgerTransport, nested schemas still exposed references.
Strict `item_name` rejection already passed. One new test initially assumed
`minimum:1`; inspection showed the equivalent existing `exclusiveMinimum:0`
integer schema. Corrected that test dialect assertion while retaining exact
equivalence and upper-bound checks, not weakening the actual constraint.

GREEN: probe/end-to-end 34 passed in 39.35s; tools/Ollama 65 passed in 4.11s.

## One-variable real/schema and skill experiments

First changed only schema exposure, with original skills. Same full real matrix:
`fix1-schema-only-real.jsonl`, exit 1, 40/53 real steps PASS, 13 FAIL, plus 23/23
simulated boundary steps PASS. Initial nested-field capture failures are gone;
wrong draft tools, quantity omissions and duplicate decisions remain. Schema
tests and original real A/B provide RED evidence; no prompt change bundled here.

`skill_micro_probe.py` is a reproducible diagnostic, not a quality substitute:
each sample uses a new temporary repository, explicitly labelled simulated
HTTP/tool setup, then a fresh real AgentConversation/E4B/tools turn with the
full four-skill context. Five fresh contexts per case/variant, native ledger and
separate oracles retained. No preselected natural Intent. Commands use existing
venv, explicit worktree PYTHONPATH, `python -P`, `--label`, `--group draft|quantity`.
Read each failed response/argument; do not score echoed prose as actions.

| Hypothesis (one skill/variable at a time) | Control | Variant | Decision |
|---|---|---|---|
| H1 active proposal vs saved rows needs a conditional patch recipe (propuestas) | Six cases each 0/5 | Weekly, pending-add edit, selected-increment edit, existing duplicate each 5/5; internal duplicate and saved query 0/5 | Retain positive recipe; 20/30 vs 0/30 |
| H2 optional quantity omitted when selection/base unresolved; make requested-quantity slot explicit (cambios) | Ambiguous increment, replacement, unknown base each 0/5 | Each 5/5 | Retain; 15/15 vs 0/15 |
| H3 internal duplicates need an exact duplicate_decision JSON example (propuestas) | Internal duplicate 0/5 | Initially simplified setup 5/5; exact original context 0/5 | Revert unproven example |
| H4 saved-list scope needs an observable lines-vs-proposal recipe (consultar) | Saved query 0/5 | Fresh-context query 0/5; full matrix introduced a duplicate/early-write regression | Revert entire addition; stop further tweaking |

H1/H2 made clear improvements before H3; thus the no-improvement-after-three
stop condition was not reached at that point. One separately labelled H4 test
was attempted for the distinct remaining query failure, then reverted. No new
hypothesis was tried after H4 failed. No phrase whitelist/catalog/framework.

Initial micro fixtures simplified original texts/units. H3's apparent improvement
did not generalize to the full original trace. Diagnostic fixtures were corrected
to match original initial messages, explicit envase units, actual row quantities/
variants and intervening unresolved yes. Five fresh exact-context samples **with
and without** H3 both failed the same duplicate slot. This falsifies that proposed
fix; its source addition is NOT retained. `fix1-h3-realistic-contract.jsonl` and
`fix1-h3-realistic-control.jsonl` preserve this evidence. Older simplified samples
remain labelled/retained, not counted as final full acceptance.

H4's full-matrix regression (`fix1-h4-full-real.jsonl`) is retained honestly:
existing duplicate capture selected `proponer_cambio/set_quantity` rather than an
add with unresolved duplication; the next scripted yes changed saved quantity
1 to 2 at a turn whose oracle forbids a commit. Its safety check FAILS. Reverting
H4 restores the retained configuration; do not present that experimental branch
as safe/accepted merely because the application's explicit confirmation gate ran.

H2 intermediate full matrix: 50/53 real steps PASS, three FAIL, in
`fix1-h2-full-real.jsonl`. No intermediate diagnostic replaces the final two runs.

## Final frozen outcomes (same in both real runs)

| Case | Real pass 1 | Real pass 2 | Offline |
|---|---:|---:|---:|
| greeting_query | 2/2 | 2/2 | 2/2 |
| weekly | 4/4 | 4/4 | 4/4 |
| explicit | **2/3 FAIL** | **2/3 FAIL** | 3/3 |
| negative | 2/2 | 2/2 | 2/2 |
| conditional | 2/2 | 2/2 | 2/2 |
| variants | 2/2 | 2/2 | 2/2 |
| selection | 4/4 | 4/4 | 4/4 |
| known_increment | 2/2 | 2/2 | 2/2 |
| unknown_base | 5/5 | 5/5 | 5/5 |
| replace | 2/2 | 2/2 | 2/2 |
| internal_duplicate | **2/4 FAIL** | **2/4 FAIL** | 4/4 |
| existing_duplicate | 4/4 | 4/4 | 4/4 |
| edit | 4/4 | 4/4 | 4/4 |
| ttl | 2/2 | 2/2 | 2/2 |
| changed | 2/2 | 2/2 | 2/2 |
| reserved | 2/2 | 2/2 | 2/2 |
| deleted | 2/2 | 2/2 | 2/2 |
| restart_replay | 4/4 | 4/4 | 4/4 |
| injection | 1/1 | 1/1 | 1/1 |

Each final run additionally has 23/23 explicitly simulated boundary steps PASS:
owner 3, malicious 5, atomic 3, old_jobs 3, batch_changed/reserved/deleted 3 each.
These are not real quality. Final offline 76/76 PASS, NOT_TESTED real quality.
Each real run exits 1: **50/53 real PASS, three FAIL**. No overall success-percentage
claim, no override by safety. Final safety, budget and complete-controller/context
checks pass on all 53 real steps in each run.

Remaining reproducible root causes/limits:

- `explicit`, update 2: novel saved-list query chooses `consultar_propuesta` and
  replies with pending lentils/tomato despite empty saved rows. Wrong tool and
  operational facts FAIL; no oracle relaxation. Context-sensitive scope
  interpretation remains unresolved by the tested recipe.
- `internal_duplicate`, update 3: correct completar tool but patches repeat
  quantities/units without required `duplicate_decision:"separate"` on both
  positions. Controller correctly leaves review unset; reply/required state FAIL.
  The following yes (update 4) cannot commit and also FAILS the requested outcome.
  Explicit JSON example did not correct the exact original context in five reps;
  no further prompt modifications authorized by evidence in this dispatch.

The retained schema/skill improvements are not sufficient for delivery. Resolving
these two model interpretation/argument-retention limits requires controller
decision and further bounded investigation, not schema aliases, a parser pass,
model authority, permissive oracles or automatic deployment.

## Final verification, hashes, latency and limits

Focused command:
```text
python -m pytest tests/test_agent_probe.py tests/test_agent_end_to_end.py tests/test_agent_tools.py tests/test_agent_ollama.py tests/test_agent_skills.py tests/test_agent_conversation.py tests/test_agent_runtime.py -q
```
**123 passed in 78.79s**, exit 0. Global suite after the final expiry correction:
`python -m pytest -q`: **1202 passed in 361.11s**, exit 0, no warnings/failures.
Earlier verification before that self-review correction: 122 focused passed in
80.62s and 1201 full-suite passed in 365.15s. The additional correction required
fresh final focused/full verification; no earlier run is omitted or reused as
proof for changed code. Both frozen real artifacts were regenerated after it.
`python -m ruff check .`: **All checks passed**, exit 0.
`git diff --check` and staged diff check: exit 0. No install/wheel build.

Final offline and both real records have equal hashes (verified against source):

- skills `85b9d07933db93e2fdb8fe43db9b5227a1bda31d5bc9b307f155e5be649d2e11`
- schemas `e3ee0912ac927dae1a61bdcde46cc7742cdcfde9c81ed846b4a1e24175706abb`
- matrix script `f3da4a021b00a09d53316fa2f8618ad39154d2207146cefaa59db3345d4c8d8c`
- prompts/oracles `d43021eb7e60407422e5f33563173c68aa61d6a252bbef52bd8350c1d0eaeb22`
- system/model digest unchanged; actual production-module hashes retained in
  each metadata record. Historical source_baseline is bd3b994, not a claim that
  fixed production files are unchanged.

Native request context maxima: real 14,106 bytes, below the 24,000 messages+tools
bound; every full controller snapshot/candidate set remains recorded. Timings:
pass 1 first 28,945.447 ms (load_duration 27.685 s), subsequent min/median/max
97.346/337.496/898.307 ms; pass 2 first 353.038 ms, subsequent
89.978/346.758/892.457 ms. First-pass load was cold-like and subsequent/second-pass
requests warm-like, not promises. Schema-only first request 32,905.676 ms was cold-like;
no unload, restart, model activation or process change was performed.

No Settings/private DB/Telegram/browser/checkout access by the probes; only
synthetic temporary repositories and approved fixed local E4B endpoint. No agents,
merge/push/deploy. Distribution check still DEFERRED (no installs/setuptools).
All original artifacts plus rejected-variant evidence remain available for review.
