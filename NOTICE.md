# Notice

LexBench is licensed under the Apache License, Version 2.0 (LICENSE), except for the MHSB
material and the LegalBench material described below, which keep their own terms.

## MHSB material (not licensed under Apache-2.0)

The following paths hold MHSB Solutions material or material derived from it:

- `sources/mhsb/`: the intake questions, deadline categories and attorney-review flags of
  the pack fragments, and the trigger phrases and command names, imported by
  `tools/import_mhsb.py` from MHSBai/platform-plugins;
- `data/fragments/` and `data/routing/`: the cases generated from that material;
- the results derived from them: `results/fragments/`, `results/routing/`,
  `results/raw/fragments/`, `results/raw/routing/`, `results/superseded/fragments/`, and the
  fragment and routing figures in `results/summary.json`, `results/table.md`, `README.md`
  and `docs/post-draft.md`.

The flag, category and command identifiers that also appear in
`sources/fragments/templates.yaml` and `sources/routing/` are part of the same material.

This material is MHSB Solutions material, published here by its owner for evaluation, under
the terms of the source-available license notice `LICENSE-SOURCE-AVAILABLE.md` of the
plugins it comes from in MHSBai/platform-plugins (SPDX identifier
`LicenseRef-MHSB-Source-Available`). It is not licensed under the Apache License,
Version 2.0. Those terms permit reading the material; copying, modifying, redistributing or
sublicensing it requires written permission from MHSB Solutions. All case data generated
from it is synthetic; every name, date and fact is invented.

## LegalBench

The LegalBench family uses tasks from LegalBench, a collaboratively built benchmark for
legal reasoning in large language models:

> Neel Guha, Julian Nyarko, Daniel E. Ho, Christopher Ré, Adam Chilton, Aditya Narayana,
> Alex Chohlas-Wood, Austin Peters, Brandon Waldon, Daniel N. Rockmore, Diego Zambrano,
> Dmitry Talisman, Enam Hoque, Faiz Surani, Frank Fagan, Galit Sarfaty, Gregory M. Dickinson,
> Haggai Porat, Jason Hegland, Jessica Wu, Joe Nudell, Joel Niklaus, John Nay, Jonathan H.
> Choi, Kevin Tobia, Margaret Hagan, Megan Ma, Michael Livermore, Nikon Rasumov-Rahe, Nils
> Holzenberger, Noam Kolt, Peter Henderson, Sean Rehaag, Sharad Goel, Shang Gao, Spencer
> Williams, Sunny Gandhi, Tom Zur, Varun Iyer and Zehua Li. LegalBench: A Collaboratively
> Built Benchmark for Measuring Legal Reasoning in Large Language Models. 2023.
> arXiv:2308.11462.

- Dataset: https://huggingface.co/datasets/nguha/legalbench
- Repository: https://github.com/HazyResearch/legalbench
- License: each task used here is licensed by its contributors under the Creative Commons
  Attribution 4.0 International License (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/. The evidence for each task, with the URL
  read and the time, is in `data/legalbench/LICENSES.md`.
- Changes: LexBench renders the upstream test examples into the upstream base prompts
  without modification. It uses a fixed random sample of at most 100 test examples per task
  (seed 20261110) and excludes one case that repeats a demonstration of its base prompt
  (`data/legalbench/LICENSES.md`, "Excluded cases"). The examples and prompts are
  materialised locally by `lexbench build` from pinned upstream revisions and are not
  committed.
- Redistributed material: the per-case records in `results/legalbench/` and
  `results/superseded/legalbench/` contain the upstream gold label of each sampled case,
  keyed by its upstream index. Those labels remain under CC BY 4.0 with the attribution
  above; they are not licensed under Apache-2.0.

Task sources, as stated in each task README at the pinned commit, and the citations the
task READMEs ask users to add:

| Task | Source | Citation requested by the task README |
|---|---|---|
| corporate_lobbying | John Nay | none |
| hearsay | Neel Guha | none |
| diversity_1 | Neel Guha | none |
| personal_jurisdiction | Neel Guha | none |
| ucc_v_common_law | Spencer Williams | none |
| telemarketing_sales_rule | Jonathan H. Choi | none |
| proa | Neel Guha, Diego Zambrano | none |
| cuad_audit_rights | Atticus Project, CUAD (https://www.atticusprojectai.org/cuad) | Hendrycks et al. 2021, below |
| insurance_policy_interpretation | Vague Contracts (https://github.com/madiganbrodsky/vague_contracts) | none |
| function_of_decision_section | Gregory M. Dickinson | none |
| oral_argument_question_purpose | Gregory M. Dickinson | none |
| overruling | CaseHOLD (https://github.com/reglab/casehold) | Zheng et al. 2021, below |

- Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball. CUAD: An Expert-Annotated NLP
  Dataset for Legal Contract Review. arXiv preprint arXiv:2103.06268, 2021.
- Lucia Zheng, Neel Guha, Brandon R. Anderson, Peter Henderson and Daniel E. Ho. When Does
  Pretraining Help? Assessing Self-Supervised Learning for Law and the CaseHOLD Dataset of
  53,000+ Legal Holdings. In Proceedings of the Eighteenth International Conference on
  Artificial Intelligence and Law (ICAIL 2021), pages 159-168, 2021.
