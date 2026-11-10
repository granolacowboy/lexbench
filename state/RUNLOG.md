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
- Grading showed most responses empty. The Claude 5.5 models think adaptively by default,
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
