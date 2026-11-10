# LegalBench task licenses

LegalBench tasks carry individual licenses. Each license below was read from the task
README in the upstream repository at the pinned commit by `lexbench build`. Only tasks
licensed CC BY 4.0 or more permissively are included. Every build reads each license
again; the time shown is when the evidence shown was first recorded, and it is renewed
when the license or URL changes or when the build is run with `--refresh`.

- Upstream repository: https://github.com/HazyResearch/legalbench, commit `b46bf4ffae90524b2b72aaa30e7745fe9db64481`
- Dataset: https://huggingface.co/datasets/nguha/legalbench, revision `daec8237410aa23e3faf4bc41ad8b3a7e1696826`
- Attribution: LegalBench (Guha et al. 2023), https://arxiv.org/abs/2308.11462

| Task | Reasoning type | License | Included | Evidence URL | Fetched (UTC) |
|---|---|---|---|---|---|
| corporate_lobbying | issue-spotting | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/corporate_lobbying/README.md | 2026-11-10T16:27:41Z |
| hearsay | rule-application | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/hearsay/README.md | 2026-11-10T16:27:42Z |
| diversity_1 | rule-application | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/diversity_1/README.md | 2026-11-10T16:27:43Z |
| personal_jurisdiction | rule-application | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/personal_jurisdiction/README.md | 2026-11-10T16:27:43Z |
| ucc_v_common_law | rule-application | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/ucc_v_common_law/README.md | 2026-11-10T16:27:44Z |
| telemarketing_sales_rule | rule-application | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/telemarketing_sales_rule/README.md | 2026-11-10T16:27:45Z |
| proa | interpretation | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/proa/README.md | 2026-11-10T16:27:45Z |
| cuad_audit_rights | interpretation | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/cuad_audit_rights/README.md | 2026-11-10T16:27:46Z |
| insurance_policy_interpretation | interpretation | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/insurance_policy_interpretation/README.md | 2026-11-10T16:27:47Z |
| function_of_decision_section | rhetorical-understanding | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/function_of_decision_section/README.md | 2026-11-10T16:27:48Z |
| oral_argument_question_purpose | rhetorical-understanding | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/oral_argument_question_purpose/README.md | 2026-11-10T16:27:48Z |
| overruling | rhetorical-understanding | CC BY 4.0 | yes | https://raw.githubusercontent.com/HazyResearch/legalbench/b46bf4ffae90524b2b72aaa30e7745fe9db64481/tasks/overruling/README.md | 2026-11-10T16:27:49Z |

## Changes made to the upstream material

LexBench renders each sampled test example into the upstream base prompt without
modification. It keeps a fixed random sample of at most 100 test examples per task (seed
20261110) and drops the excluded cases below from that sample.

## Excluded cases

- `lb-decisionfn-0366`: The test input "For these reasons, we AFFIRM." (label Decree) is
  also the last demonstration in the upstream base prompt for
  function_of_decision_section, so the case would test recall of the prompt rather than
  classification.
