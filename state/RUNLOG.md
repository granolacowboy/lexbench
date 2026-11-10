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
