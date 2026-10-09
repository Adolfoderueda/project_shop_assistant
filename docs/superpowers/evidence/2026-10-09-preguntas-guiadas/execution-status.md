# Guided acceptance execution status

Base: `14404f5c44988f2d737f3c0073dbe17d7569ea4b`. No deployment authorization.

## Freeze (before evaluation)

- Matrix v1 frozen 2026-10-09 15:45:30 +02:00, SHA256
  `92a62a4e35e8af5d8d5313876aed779748f51e62b3f0570dd01eb71df0fd8193`.
- Development offline v1 exposed harness-only missing callback acknowledgement and
  a callback incorrectly attached to the latest query message instead of the delivered
  question. Both reproduced RED and fixed in the probe, not the application.
- Matrix v2 is **additive**, frozen 2026-10-09 15:59:22 +02:00, SHA256
  `f21df63882f2269e7bd38cfa25eed21f4822e21b67f686d5f5deb224cff6c53e`.
  All 20 original case inputs/expectations are unchanged. Six additional cases close
  coverage gaps: saved-list query/duplicate, query+answer, unknown unit, second topic,
  replacement, reordered answer. No failed expectation was relaxed.
- Probe freeze SHA256
  `5496d090e75e06e4b524dced7866a1d27bfd146c432e887f6455ab9fd5683278`.
- Each final JSONL manifest contains the entire literal frozen matrix, source hashes,
  fixed model/parameters and execution time. No prompt/controller tuning authorized.

## Interpretation of evidence

26 cases, separate button and offered-text paths (legacy expiry text-only), three
repetitions. General collective language is reported separately from bounded replies
and security. Simulated buttons and offered labels are application selections, **not
model understanding**. Offline native HTTP fixtures exercise the actual interpreter,
repository, conversation, TelegramIO parser/ack/outbox and stub send receipts, not E4B.
Real mode calls only the already available fixed localhost model. Temperature-zero
repetitions measure stability, not independent statistical samples.

On failure, remaining steps are explicitly unexecuted, never silently dropped. Invalid
outputs/fallbacks and security rejections do not become interpretation successes.
An unsupported unit and expired legacy answer have explicit security-only expectations;
their conservative fallbacks are counted, not advertised as understanding.

Final results and authorization limits are recorded in `results.md`. Independent
verification returns1 for both final files: offline102/102 bounded,24/27 security,
24/24 general; real6/102 bounded,6/27 security,0/24 general. Real114 clarifications,
12 invalid outputs and486 unexecuted later steps are not interpretation passes.
Acceptance is **BLOCKED**, not merely a packaging/deployment formality. No application
fix or prompt/matrix tuning after these runs. No Telegram launch, flag activation
or worker restart. Controller whole-branch review remains to be dispatched separately.

Original pre-review complete suite:1559passed in567.05s, timeout600000, exit0; focused14passed;
whole Ruff and both diff checks clean. No application/script/tests changed after
freeze or these runs. Packaging still unverified with no installed build tools.

## Review fix round1: verifier v3, immutable v2 execution

Only verifier/tests/documentation changed under scoped approval. No changes to
application, prompts, matrix or raw artifacts; no model rerun.46 focused tests pass,
whole Ruff/diff clean. Native schema/decoded data, actual transport/complete summary
facts and live question expiry are independently checked. Historical source integrity
uses the pinned original Git objects plus explicit exact-byte newline reconstruction,
not an exemption for the changed current verifier. See `results.md` for the method.
V3 independent verification retains12 offline/906 real errors and identical rejected
acceptance totals; original harness validation gains no newly exposed false pass.
Recorded runtime hashes verify; current-runtime differences are empty. Final complete
suite:1591passed in552.14s, timeout600000, exit0. Selective commit verification is
recorded in the local Task8 fix report. No code/tests edits after that final run.
