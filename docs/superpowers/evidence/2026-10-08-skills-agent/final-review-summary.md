# Final review fix — acceptance remains FAIL

Both unchanged frozen real matrices completed after the dialogue provenance fix.
Original evidence has not been overwritten. These are acceptance failures, not
permission to change prompts, schemas, or oracles or attempt a fifth hypothesis.

| Evidence | Exit | Real steps | Simulated boundary steps | Acceptance |
|---|---:|---:|---:|---|
| final-review-real-1.jsonl | 1 | 50/53 | 23/23 | FAIL |
| final-review-real-2.jsonl | 1 | 50/53 | 23/23 | FAIL |

Every real safety, budget, and complete-context check passed in both runs.
This does not override the three semantic failures in each run:

1. `explicit`, update 2: saved-list inquiry calls `consultar_propuesta`, showing
   draft items instead of the empty saved list. Interpretation/action/arguments/
   reply fail.
2. `internal_duplicate`, update 3: completion lacks the required separate-line
   duplicate decisions for both positions. State/reply fail; review stays unset.
3. `internal_duplicate`, update 4: subsequent yes cannot commit without review.
   State/reply fail for the required completed flow; the refusal remains correct.

## All cases (same results in both runs)

| Case | Mode | Passing/steps |
|---|---|---:|
| greeting_query | real | 2/2 |
| weekly | real | 4/4 |
| explicit | real | 2/3 |
| negative | real | 2/2 |
| conditional | real | 2/2 |
| variants | real | 2/2 |
| selection | real | 4/4 |
| known_increment | real | 2/2 |
| unknown_base | real | 5/5 |
| replace | real | 2/2 |
| internal_duplicate | real | 2/4 |
| existing_duplicate | real | 4/4 |
| edit | real | 4/4 |
| ttl | real | 2/2 |
| changed | real | 2/2 |
| reserved | real | 2/2 |
| deleted | real | 2/2 |
| restart_replay | real | 4/4 |
| injection | real | 1/1 |
| owner | simulated HTTP | 3/3 |
| malicious | simulated HTTP | 5/5 |
| atomic | simulated HTTP | 3/3 |
| old_jobs | simulated HTTP | 3/3 |
| batch_changed | simulated HTTP | 3/3 |
| batch_reserved | simulated HTTP | 3/3 |
| batch_deleted | simulated HTTP | 3/3 |

## Freeze and final-source metadata

Model metadata, parameters, endpoint, skills, schemas, system, matrix source,
prompts/oracles, and all seven shopping_agent source hashes are identical to
`fix1-final-real-2.jsonl` and identical between these two new runs. No probe source
was changed. Its existing metadata hashes shopping_agent sources, not root-level
dialogue_storage.py; the final changed-source hash is recorded here separately
rather than changing the frozen harness:

- Baseline: `1a4123f` on `feat/skills-agent`.
- Final `dialogue_storage.py` SHA256:
  `218091ebd6ca960ce475f08c07a038061232efd5dbea7ff5b75fda33305c9656`.
- Final `tests/test_command_query_provenance.py` SHA256:
  `42d218a72e848af0c9490a128824eb1ca97c6cdf6c1137e136bb3614899605ec`.
- Matrix SHA256:
  `f3da4a021b00a09d53316fa2f8618ad39154d2207146cefaa59db3345d4c8d8c`.
- Prompts/oracles SHA256:
  `d43021eb7e60407422e5f33563173c68aa61d6a252bbef52bd8350c1d0eaeb22`.
- Run 1 artifact SHA256:
  `f25635c46a2ad79cb2425df03302a30220c145418d03986dcd4bc79bf71d2d20`.
- Run 2 artifact SHA256:
  `85cae1467b4b3762ec2954b49a91f01b98ce2d0f6c50e2a06ace7d2f9bd87c25`.

First observed request: 43,978.280 / 365.543 ms. Subsequent medians:
356.296 / 424.485 ms; maximum observed context: 14,106 bytes in each run.
No model unload/restart or performance promise; full pytest ran concurrently.

Probe commands used the existing Python, `-P`, worktree PYTHONPATH, explicit safe
new output paths, and synthetic temporary databases under the approved opencode
TEMP/TMP directory. No Settings/private data, Telegram, activation, installs,
downloads, model changes, merge or push. Raw requests, responses, native tool
calls, states and independent oracle outcomes are retained in the two JSONLs.

**Remaining blocker:** architecture/product decision on saved-list versus draft
query selection and internal-duplicate tool arguments. Real acceptance is FAIL;
do not activate/deploy based on the storage fix or green unit suite.
