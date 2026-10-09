# Guided dialogue acceptance: BLOCKED

Synthetic data only. No private list/configuration, live Telegram, purchases,
activation or worker restart. See [freeze and scope](execution-status.md) and
[literal matrix](matrix.json). Default guided flag remains off.

## Offline integration (three repetitions, not E4B understanding)

| Conversations | Complete with expected state | Total |
| --- | ---: | ---: |
| Bounded responses / offered selections | 102 | 102 |
| Security scenarios | 24 | 27 |
| General-free variants with subsequent offered scope | 24 | 24 |

669/672 steps executed; three later steps explicitly unexecuted. 345 native HTTP
fixture interpretation turns; 144 simulated button steps. Nine conservative model
fallbacks (three explicit clarification fixtures for expired legacy replies, six
invalid unsupported-unit fixtures), **not** understanding successes. 144 final write
steps to isolated synthetic lists; zero observed ambiguous assignments, writes
without separate delivered-review confirmation or purchase fixture changes.
These are observations of executed traces, not an exemption for incomplete cases.

Raw [offline-v2.jsonl](offline-v2.jsonl), 673 records/10,708,636 bytes, SHA256
`e5f7d2bdfef5dc64502da5436b61db7b7f7b7e09258107f13b4e36de17d1f185`.
Independent `--verify` returns1 with the same failures and no hash mismatch.
It does not call the model or trust persisted controller validation labels.

### Application blocker, not repaired in this task

`expired-guided/button`, all three repetitions, step4: after an expired confirmation
callback is correctly rejected, `leche una` cannot start a new proposal. Authorized
history rejects a completed callback without a consumed authenticated selection;
the conversation closes with “No puedo validar el contexto anterior...” without an
HTTP call. Old carne2 remains; final confirmation step5 is unexecuted. Security was
conservative, but the required full conversation **failed**. A separately approved
application RED→GREEN fix and affected reruns are needed; matrix/prompt untouched.

## Real E4B

The existing fixed model was available; 159 `/api/chat` requests returned HTTP200.
No download, activation, prompt adjustment or matrix relaxation. Both execution and
independent `--verify` return1, with identical results and no hash mismatch.

| Real full conversations | Complete with expected state | Total |
| --- | ---: | ---: |
| Bounded responses / offered selections | 6 | 102 |
| Security scenarios | 6 | 27 |
| General-free variants with subsequent offered scope | 0 | 24 |

186/672 steps executed; **486 explicitly unexecuted** after the first failure in each
conversation. 114 clarification fallbacks had no native tool call (often literal
tool-like syntax in `message.content`); 12 native outputs failed schema validation.
33 validated candidates are **not** 33 dialogue passes. Only increment and nonreserved
source selection conversations completed (both paths, three repetitions each).
12 simulated button steps and 12 separately confirmed synthetic write steps.

Precisely observed failures:
- 22 cases fail at the first step: 19 produce no native tool calls; correction/mixed
  final invents unsupported `unit="unidad"`; saved duplicate incorrectly proposes
  set-total instead of a new duplicate; replacement uses `replacement="arroz tres"`
  and omits quantity3. No reinterpretation of model prose was used as a workaround.
- Unknown-base case reaches explicit set-total and focused `cinco`, then emits
  `proponer_cambio(...,replacement=5)` instead of a valid quantity response (six paths).
- Expired legacy answer `2` becomes a fresh arroz2 draft using the expired antecedent
  (three repetitions). No row is saved, but this **fails the frozen expiry expectation**
  and needs separate application authority/expiry review; it is not a safe pass.
- Queries, internal-duplicate decisions, collective phrases, topic/correction and
  ambiguity steps after failed starts were **not executed**, not quietly counted as
  model passes. All later original inputs are preserved in the trace.

The verifier reports zero *tagged write/witness/budget invariant violations* in the
executed subset, **not all security accepted**: only6/27 security dialogues pass;
the expired antecedent creates an unwanted draft in three cases. Ambiguity tests
mostly never reach the ambiguous turn, so this run cannot validate that threshold.
Neither historical list-query nor internal-duplicate real acceptance is resolved.

Raw [real-v2.jsonl](real-v2.jsonl), 673 records/2,748,888 bytes, SHA256
`78242888039e8ae5e743793da407b26e6391a3c9ed073f9d466da20f3b249f8f`.
The raw files retain original requests/responses, validations, state and delivery.

## Limits and deployment gate

Final source-state verification: `python -P -m pytest -q` **1559 passed in567.05s**
(timeout600000); focused verifier/harness tests14passed; whole-repository Ruff and
staged/unstaged diff checks clean. These green tests do not override the rejected
real/offline acceptance. Controller whole-branch review has not yet occurred.

Unit tests and offline fixtures do not validate model interpretation or Telegram.
Simulated callbacks and offered text labels are application selections, never
language-understanding passes. Collective free-language variants are separate from
bounded responses; do not average their failures with security. A conservative
fallback or merely no writes does not satisfy an interpretation expectation.
Temperature-zero repetitions test stability, not statistical independence.

Durable tokens require known stub message delivery, owner/chat/bot binding and current
question/version; even rejected/expired buttons must not poison later dialogue.
Live Telegram delivery, long polling across a real restart and human reading remain
unverified. Existing offline tests cover authentication, atomicity, migration,
Unicode oversized reviews, replays/uncertain send and callback acknowledgement.

Wheel/install validation remains blocked: build, wheel and setuptools absent and no
wheel available. Source migrations001–010 exist, but the packaging declarations list
skills and third-party notices, not sibling migration SQL used by storage. No tools
were installed and no packaging correctness claim is made.

The earlier agent Task7 acceptance stays open until real list queries/internal
duplicate dialogues meet their expectations. No Telegram activation is authorized.
A future launch requires separate authorization, a fresh empty independent DB,
explicit original-message and repository buy/resume guards, checkout rejection,
no store/profile opening, owner/bot binding and one worker/lock with authorized
stop/start. `dry_run` is not sufficient. Rollback uses new code with guided flag off
and schema10 retained; no downgrade or private backup restoration was performed.
