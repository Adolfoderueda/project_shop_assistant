# Final review fix wave — 2026-09-29

## Changes and RED/GREEN evidence

- Ollama receives only the current free-form text, never shopping-list rows; deterministic commands still bypass the provider. Updated populated-list payload test initially failed (`lines` present); passed after removing them.
- Model-proposed additions now clarify on alternatives, multiple products, and conditional clauses (`o`, `u`, `y`, `si`, `cuando`, `en caso de`, `a menos que`) even when the proposed description echoes the message. Original adversarial tests failed for alternatives/conditions; expanded cases failed for `u`, `y`, and `a menos que`; all passed after the guard. Tests preserve ordinary Spanish and product descriptions `Blemil tipo 1 Evolution` and `Alpha Spirit Wild Fish / Only Fish`. The former exposed an existing overbroad digit rejection, so `tipo <digit>` is treated as a product qualifier, while explicit quantities remain rejected.
- Busy `model-local` now returns failure with sanitized guidance to stop the worker. New output assertion failed on the previous generic error and passed after the targeted lock handling. The existing nested-lock test was updated to expect the new return contract.
- `configure` is the only other production caller of `save_settings`. Its final settings write now takes the worker lock and revalidates existing ownership, bot, and database lock target. A worker-lock regression test failed before the lock and passed after it was added. A first-configuration race test failed with an unbound previous configuration and then passed after checking for configuration created during interactive binding. Lock is not held during interactive prompts or Telegram binding.

## Verification

- Focused RED runs: expected failures for outgoing list, alternatives/conditions, lock message, and concurrent configure; no production changes preceded those respective tests.
- Focused GREEN: `python -m pytest tests/test_ollama_interpreter.py tests/test_conversation.py tests/test_runtime.py -q` → 112 passed (before final expanded cases); later expanded focused cases → 12 passed.
- Full suite: `.venv/Scripts/python.exe -m pytest -q` → 299 passed after final expanded cases.
- Ruff: `.venv/Scripts/python.exe -m ruff check .` → all checks passed. `git diff --check` exited 0 (Git emitted only LF/CRLF conversion warnings).

## Remaining assumptions and boundaries

- There is no Ollama installation/download, Telegram call, or local hardware/VRAM validation here. Tests use offline transports and temporary configuration.
- Direct external callers of `config.save_settings` are not automatically locked; the coordinated production CLI writers are `configure` and `model-local`. Adding an implicit lock in `save_settings` would deadlock these existing lock owners and require broader lock design. Manual edits or future third-party writers must coordinate with the worker lock.
- Text heuristics intentionally clarify some genuinely named products containing conjunctions or conditional words; users can use deterministic `/anadir` for these cases.
