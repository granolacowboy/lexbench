# Run log

## LEXBENCH-1, 2026-11-10

Step 1. Harness, families, graders and estimate.

- Branch `lexbench/harness-v1` created from `main` (placeholder README).
- Gates: ANTHROPIC_API_KEY SET. Anthropic models list (fetched 2026-11-10T16:11Z) holds
  claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5. Twelve LegalBench tasks carry
  CC BY 4.0 on record (data/legalbench/LICENSES.md). Estimate 4.74 USD at 100 examples per
  task, below the 60 USD cap, so no reduction to 50 was needed.
- Prices checked against the pricing page at 2026-11-10T16:27Z: match for all three entries.
- Data: legalbench 1,080 cases (upstream commit b46bf4f, dataset revision daec823, seed
  20261110), fragments 197 cases (seed 20261110), routing 271 cases.
- The mock entry ran every family end to end through the CLI in a scratch copy
  (1,548 of 1,548 correct in oracle mode).
- Third-party LegalBench records contain dash characters in upstream text. They are kept
  unmodified, excluded from version control and verified by hash; the dash lint covers
  every file LexBench authors.
- Public-repository check: the pilot firm identifiers are held in the private
  specification, which is outside this workspace and was not read. Proxy checks
  found no hits: none of the platform-plugins endpoint hosts, and no person or firm name
  from the platform-plugins evals, occur in lexbench. Three invented names that coincided
  with names in platform-plugins were replaced. Handoff: run the private denylist grep
  against this repository (see the pull request).
- Commit f618b0b "lexbench: harness v1 (families, graders, estimate)" pushed to
  `lexbench/harness-v1`. CHECKPOINT 1 passed, with the firm-identifier grep handled as above.

Step 2. Batch runs.

- 16:35Z: nine batches submitted (three families on three Claude entries), all recorded in
  state/batches.json. At 16:40Z all had ended with no errors. A poll defect (the client was
  released while the results stream was read) was fixed before the download.
- Grading showed many responses empty (corrected in FIX-LEXBENCH-1: 1,608 of 4,644
  superseded responses, 34.6%, between 0.5% and 69.9% by entry and family). The Claude 5.5 models think adaptively by default,
  and thinking consumed the per-family output bound (24, 120 and 20 tokens). The nine
  batches are kept in state/batches.json, marked superseded, with raw results under
  results/raw. Their cost counts toward the cap; they are not reported.
- Two diagnostic probes (16 requests in total, about 0.03 USD, recorded in state/runs.json;
  submission times approximate) established the lowest thinking setting per model: thinking
  disabled on Haiku 5.5, between_tools on Sonnet 5.5, and effort low on Opus 5.5, which
  rejects disabled.
- Changes before resubmission: per-entry thinking settings in models.yaml;
  `reasoning_tokens` (1,024 on Opus 5.5) added to the family output bound; fragment output
  bound raised from 120 to 600 tokens; a settings fingerprint on every submission, so that
  changed settings permit a new run.
- 16:45Z: nine batches resubmitted; all ended with no errors by 16:49Z (first poll).
  CHECKPOINT 2 passed: 18 batches recorded, recorded estimates 26.78 USD for batches plus
  0.03 USD for probes, below 60 USD. Spend computed from reported usage at batch prices:
  about 4.49 USD for the reported batches, 4.35 USD for the superseded batches, 0.03 USD
  for probes; 8.88 USD in total.

Step 3. Grading, report and documents.

- Grader normalisation was settled after inspecting the format failures, and before the
  results were reported. The rules apply to every model equally: a repeated answer cue of
  one to four words and a colon is removed (the upstream prompts end with cues such as
  "A:", "Label:", "FINAL ANSWER:" and "Governed by:"). When the first line holds only a
  cue, the next line is read. A label at the start of the line is read as the answer. For
  fragment cases, the last JSON object in the response is the answer. A response that
  reaches the output bound before any label counts as incorrect and is reported as a
  format failure.
- `lexbench report` wrote results/summary.json, results/table.md and the README table.
  docs/post-draft.md takes every figure from results/summary.json.

## FIX-LEXBENCH-1, 2026-11-10

Response to review XREVIEW-LEXBENCH-1 on pull request #1 (head 224b4da).

Step 1. Harness corrections, each with a regression test in tests/test_review_fixes.py
written before the fix (24 of 26 failed at 224b4da; the two that passed guard behaviour
that must not change).

- Reproduced before fixing: F1 (paid mock entry, reasoning room added after the estimate),
  F5 (failed synchronous run left running), F6 and F13 (grader on the review's inputs and
  on the four Opus records), F12 (only lb-decisionfn-0366 repeats a demonstration in full;
  five insurance cases share only a policy sentence with a demonstration), F14, F15
  (a rebuild rewrote LICENSES.md and built_at), F16, F17 and F18.
- F10: the Claude 5.5 models reject any non-default temperature, and API version
  2026-10-21, which the pinned SDK sends, rejects the parameter at any value
  (platform.claude.com/docs/en/build-with-claude/thinking, "Sampling parameters").
  The Anthropic adapter therefore sends none; the openai_compatible adapter sends 0.
- Thinking settings checked against platform.claude.com/docs/en/build-with-claude/effort:
  all three 5.5 models accept adaptive thinking at effort low; Opus 5.5 rejects thinking
  disabled. Adaptive thinking at effort low is therefore the one setting common to all
  three. No probe request was made.
- Commit 968dc8d (harness fixes, licensing, data rebuild) and commit e9eb23a (equal
  settings for legalbench and fragments) pushed before any rerun batch was submitted. The
  LegalBench grading rule was settled in 968dc8d.
- Data: legalbench 1,079 cases (sha256 36b9ace52e687be2, lb-decisionfn-0366 excluded);
  fragments 197 cases (sha256 71fa9bc5d37851ee, kind no longer printed, non-oracle choice
  sets); routing unchanged (fc9ba25cca7572b2). A second build changed no tracked file.

Step 2. Rerun through the Message Batches API.

- Estimate at 17:47Z: pricing check match; rerun estimated at 25.34 USD; with 26.81 USD
  recorded, 52.15 USD in total, below the 60 USD cap. No sample reduction was needed.
- ANTHROPIC_API_KEY SET, sourced only in the submission and polling subshells.
  `lexbench models` verified the three Claude identifiers before submission.
- 17:50Z: six batches submitted, each recorded as pending before the provider call:
  legalbench msgbatch_01L8bEnzY1KhuMewXccYHJ2M (Opus), msgbatch_014xYHjABG1CuiqGNzkMa4C6
  (Sonnet), msgbatch_01UPehMdEtWMHtN1VyNDnYit (Haiku); fragments
  msgbatch_01KMFW6RWK7f1RjkmBRN3k12 (Opus), msgbatch_01BDdTPEsCmy3NuXeLgPZQsW (Sonnet),
  msgbatch_01RZ2NAWvk1KZgZHx57vjo9c (Haiku).
- Polls at 17:55Z (four ended), 18:00Z and 18:05Z (all six ended). 3,828 of 3,828
  requests succeeded; none errored, none was empty, none reached its output bound.
- The six LegalBench and fragment batches of 16:45Z are marked superseded; their per-case
  records moved to results/superseded/. Routing was not rerun; regrading left its
  per-case records unchanged.
- Spend from reported usage at batch prices: 4.02 USD for the rerun, 12.90 USD in total
  with the earlier batches and probes (4.35 first run, 3.75 superseded 16:45Z batches,
  0.74 routing at 16:45Z, 0.03 probes). Recorded estimates: 52.15 USD.

Step 3. Grading and documents.

- Grader ablation on the reported LegalBench responses (correct of 1,079): strict
  728, 657, 709; first commit f618b0b 822, 695, 782; 224b4da 898, 789, 845; current
  902, 903, 856 (Opus, Sonnet, Haiku). Disclosed in README.md and docs/post-draft.md.
- Observed after the rerun and left unchanged, because a rule change now would be post hoc:
  lb-proa-0009 (Opus) begins with a zero-width space before "A: Yes", so its cue is not
  removed and it counts as a format failure although its label is correct.
- `lexbench report` regenerated results/summary.json, results/table.md and the README
  table. docs/post-draft.md takes every figure from results/summary.json, from the
  per-case records or from the ablation above.
- The private exposure grep (35 identifiers from the private specification) is not
  available in this workspace; the substitute check of LEXBENCH-1 was repeated (see the
  pull request comment). The private grep remains a step for Richard Berman.

## FIX-ULTRA-LEX, 2026-11-11

Response to the ultrareview comment on pull request #1 (harness code subset), head
e235f92, with the operator's reading note: L1 to L8 standing, L9 and L10 conditional on
upstream data. Local headless run; no API key; every test through the mock provider.

Step 0. Inputs and baseline.

- `git fetch origin`; lexbench/harness-v1 checked out at e235f92 (equal to the remote
  head; nothing to merge). No earlier FIX-ULTRA-LEX entry in this log.
- Baseline at e235f92: `uv run pytest -q` 106 passed; `ruff check` and `ruff format
  --check` clean; `mypy` (strict) no issues in 36 source files.
- Scratch copy of e235f92 outside the repository: `lexbench build --family legalbench`
  gave 1,079 cases, sha256 36b9ace52e687be2, as recorded; data/MANIFEST.json and
  data/legalbench/LICENSES.md unchanged. `lexbench grade` for the three Claude entries
  there reproduced all 42 tracked files under results/ byte for byte, so grading of the
  recorded responses is deterministic.

Step 1. Failing tests (tests/test_ultrareview_fixes.py, written before any fix).

- Against e235f92: 36 failed, 1 passed (the passing test guards the registry of record
  against the new params rule and must keep passing). Failure per finding:
  L1 resubmission after a failed second of three chunks: record has no chunk_index, and
  with chunk 1/3 recorded the rerun submits nothing (1 == 2).
  L2 estimate priced as batch accepted after `batch: false`: DID NOT RAISE CapExceeded.
  L3 options.params max_tokens 100000, budget_tokens 32000, max_completion_tokens and
  family_settings.params max_tokens 5000 all sent: DID NOT RAISE ProviderError (both
  adapters, request and estimate).
  L4 options.retries 4, 10, -1 and "3" accepted by the schema; Anthropic client
  max_retries 4; Estimate has no attempt count; an estimate without it is not refused.
  L5 a running record of a dead process and one with a heartbeat from 2026-01-01 stay
  running; a live running record does not block a second run; no heartbeat.
  L6 a pending record with a batch id is skipped by poll and blocks run; the refusal
  names neither batch_id nor status.
  L7 RegistryError "unknown model entry 'renamed-away'" aborts poll.
  L8 `lexbench grade` exits 0 with no current submission; report publishes a stale file
  and a file not written by grade; no grade marker exists.
  L9 scrub replaces "Draft", "NDA", "LLC", "Please", "PI", "What".
  L10 no check of command names against the grader's pattern exists.
