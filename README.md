# LexBench

LexBench is a model-agnostic harness for evaluating language models on legal tasks. It
builds three task families, sends them to any model listed in a YAML registry, grades the
responses with deterministic graders, and reports accuracy per task and family.

## Families

| Family | Source | Cases | Expected answer | Grader |
|---|---|---:|---|---|
| `legalbench` | 12 LegalBench tasks licensed CC BY 4.0 (Guha et al. 2023) | 1,079 | the task label | label match over the whole response (see Grading) |
| `fragments` | synthetic intake and deadline cases from 12 MHSB practice-pack fragments | 197 | deadline category and kind, or the set of attorney-review flags | category and flag match |
| `routing` | MHSB trigger phrases, routing-suite phrases and written paraphrases | 271 | one command name | command match |

**LegalBench.** The tasks cover four reasoning types: issue spotting (`corporate_lobbying`),
rule application (`hearsay`, `diversity_1`, `personal_jurisdiction`, `ucc_v_common_law`,
`telemarketing_sales_rule`), interpretation (`proa`, `cuad_audit_rights`,
`insurance_policy_interpretation`) and rhetorical understanding
(`function_of_decision_section`, `oral_argument_question_purpose`, `overruling`). Each task
uses its upstream base prompt, whose in-context examples are upstream's few-shot
demonstrations from the train split. Each task contributes at most 100 test examples, drawn
as a fixed random sample (seed 20261110) when the split is larger. One sampled case,
`lb-decisionfn-0366`, repeats the last demonstration of its base prompt and is excluded, so
the family has 1,079 cases. The license of every task is read from its upstream README at
build time and recorded in [data/legalbench/LICENSES.md](data/legalbench/LICENSES.md), with
the changes made and the excluded cases.

**Fragment cases.** `lexbench/families/fragments.py` generates the cases from each fragment's
intake questions, deadline categories (kind `statutory` or `firm_set`) and attorney-review
flags, using the templates in `sources/fragments/templates.yaml`. The seed is 20261110. A
deadline case lists the fragment's categories by id and name, defines the two kinds in
general terms (a period fixed by statute or court rule, or a date the firm sets or enters
from a notice, order, contract or document), describes an event, and asks for the category
and its kind; the kind of each category is not shown, so it is judged. An intake case
gives firm settings, the flag rules and an intake record, and asks for every flag whose
rule is met (possibly none). Sensitive intake questions are never shown. All names, dates
and facts are invented.

**Routing.** Each phrase is paired with the single command expected when all 24 commands are
installed. The prompt lists the commands with one-line descriptions written for LexBench.

`lexbench build` writes every family to `data/` and records counts and SHA-256 hashes in
`data/MANIFEST.json`. A run refuses data that does not match the manifest. A rebuild that
produces the same content leaves the tracked files unchanged: the manifest's `built_at` and
the license fetch times in `data/legalbench/LICENSES.md` are renewed only when the content or
the license evidence changes, or with `lexbench build --refresh`.

## Model registry

Models are configuration, not code. Each entry in [models.yaml](models.yaml) is keyed by the
name that results are filed under:

```yaml
models:
  claude-sonnet-5-5:
    provider: anthropic            # adapter in lexbench/providers/
    model: claude-sonnet-5-5       # the provider's identifier
    auth: ANTHROPIC_API_KEY        # name of an environment variable, never a value
    pricing: {input_per_mtok: 2.00, output_per_mtok: 10.00, batch_discount: 0.5}
    max_tokens: 1024               # output ceiling; each family sets a lower bound
    reasoning_tokens: 0            # optional room added to the family bound for reasoning
    concurrency: 4                 # parallel requests for synchronous runs
    rate_limit_rpm: 50             # optional
    batch: true                    # use the provider's batch mode when it has one
    options:
      params: {thinking: {type: between_tools}}   # merged into every request
```

**Thinking settings and output bounds.** The Claude 5.5 models think adaptively by default,
and thinking counts toward `max_tokens`. An entry may set `family_settings` for one family:
`max_tokens` fixes that family's output bound, and `params` replaces `options.params`.

| Family | Thinking setting, all three Claude entries | Output bound per request |
|---|---|---|
| `legalbench` | adaptive thinking at effort `low` | 1,048 tokens on every entry |
| `fragments` | adaptive thinking at effort `low` | 1,624 tokens on every entry |
| `routing` | entry level: Opus 5.5 effort `low`; Sonnet 5.5 thinking `between_tools`; Haiku 5.5 thinking `disabled` | Opus 5.5 1,044 tokens (20 plus 1,024 of reasoning room); Sonnet 5.5 and Haiku 5.5 20 tokens |

Adaptive thinking at effort `low` is the one thinking setting that all three models accept:
Opus 5.5 rejects thinking `disabled`, and Sonnet 5.5 offers `between_tools` as its lowest
setting. LegalBench and fragment cases therefore give every model the same settings and the
same output room. The routing results were measured at the entry-level settings and with
unequal output room, and are reported as such.

**Sampling.** The `anthropic` adapter sends no `temperature`: the pinned SDK uses API
version 2026-10-21, under which a request that sets `temperature`, `top_p` or `top_k`
returns an error, and the Claude 5.5 models reject a non-default temperature under every
API version. Claude entries therefore run at the provider's fixed default sampling, and
repeated runs need not give identical responses. The `openai_compatible` adapter sends
`temperature: 0`.

The registry ships three Claude entries (`claude-opus-5-5`, `claude-sonnet-5-5`,
`claude-haiku-5-5`), a commented example of a self-hosted endpoint, and a `mock` entry.
`lexbench models` validates every entry against the schema in `lexbench/registry.py`.
Anthropic identifiers are checked against `GET https://api.anthropic.com/v1/models`, and
OpenAI-compatible identifiers against `GET <endpoint>/models` when the endpoint is
reachable. A malformed entry is refused with a short message that names the entry and the
field.

**Adding a model** takes one entry. For example, a self-hosted model behind vLLM, Ollama, the
llama.cpp server, TGI or any other OpenAI-compatible server:

```yaml
  local-llama-3-70b:
    provider: openai_compatible
    model: meta-llama/Llama-3.3-70B-Instruct
    endpoint: http://localhost:8000/v1   # base URL serving /chat/completions and /models
    # auth: LOCAL_LLM_TOKEN              # only when the server needs a bearer token
    pricing: {input_per_mtok: 0, output_per_mtok: 0}   # self-hosted counts as zero
    max_tokens: 1024
    concurrency: 8
    batch: false
```

The same adapter covers hosted OpenAI-compatible services such as OpenRouter; set
`endpoint`, `auth` and `pricing` to match the service.

**Adding a provider** takes one class. Subclass `Provider` in `lexbench/providers/base.py`
and implement its interface: `estimate` (a default is provided), `run_sync`, and, for batch
support, `submit_batch`, `poll_batch` and `fetch_batch`. Then register the class in
`PROVIDERS` in `lexbench/providers/__init__.py`. Three adapters are included:

- `anthropic`: the Messages API, and Message Batches when `batch: true`;
- `openai_compatible`: chat completions over plain HTTP (httpx), synchronous with bounded
  concurrency and retries, no batch mode;
- `mock`: deterministic responses (`oracle`, `constant` or `hash` mode) for tests and dry
  runs.

## Spend control

`lexbench estimate` counts tokens per family and entry and writes `results/estimate.json`;
it submits nothing. Input tokens are estimated as characters divided by three plus 16 per
request, and output tokens as the family's `max_tokens` plus the entry's
`reasoning_tokens`, or a family's fixed bound, so the estimate is an upper bound. The
estimate records, for every entry and family, the entry's settings fingerprint and its
pricing; `lexbench run` refuses an estimate whose fingerprint or pricing differs from the
registry.
Claude prices are checked against https://platform.claude.com/docs/en/about-claude/pricing
and the result is recorded with the fetch time. Before each submission, `lexbench run` adds
the submission's estimate to the estimates already recorded in `state/batches.json` and
`state/runs.json`. It refuses when the sum would exceed `limits.spend_cap_usd` (USD 60) or
when the estimate is stale. A batch holds at most 10,000 requests, and entries with zero
pricing count as zero. Each submission is recorded with its batch or run id, family, model
name, request count, estimated cost and a fingerprint of the entry's settings for the
family. A batch is recorded as `pending` before the provider is called and updated with the
provider's batch id afterwards; a submission whose provider call fails is recorded as
`failed`, and a synchronous run that fails is recorded as `failed` rather than left
`running`, so that it does not block grading. A `pending` record without a batch id blocks a
new submission for its family and entry until it is resolved. Repeating `run` therefore
submits nothing new, while a change of settings or data permits a new submission. Every
recorded submission, including superseded, failed and pending ones, counts toward the cap.
The cap applies to submissions made through the harness; the two diagnostic probes of the
first session were made outside it and were recorded by hand in `state/runs.json`.

## Results

<!-- results:start -->
| Family | Task or group | n | claude-opus-5-5 | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---|---:|---:|---:|---:|
| LegalBench | corporate_lobbying (issue-spotting) | 100 | 0.810 | 0.790 | 0.760 |
| LegalBench | cuad_audit_rights (interpretation) | 100 | 1.000 | 0.990 | 0.990 |
| LegalBench | diversity_1 (rule-application) | 100 | 1.000 | 1.000 | 1.000 |
| LegalBench | function_of_decision_section (rhetorical-understanding) | 99 | 0.556 | 0.576 | 0.455 |
| LegalBench | hearsay (rule-application) | 94 | 0.883 | 0.862 | 0.862 |
| LegalBench | insurance_policy_interpretation (interpretation) | 100 | 0.660 | 0.590 | 0.540 |
| LegalBench | oral_argument_question_purpose (rhetorical-understanding) | 100 | 0.460 | 0.520 | 0.350 |
| LegalBench | overruling (rhetorical-understanding) | 100 | 0.950 | 0.950 | 0.980 |
| LegalBench | personal_jurisdiction (rule-application) | 50 | 0.980 | 1.000 | 0.920 |
| LegalBench | proa (interpretation) | 95 | 0.937 | 0.979 | 0.937 |
| LegalBench | telemarketing_sales_rule (rule-application) | 47 | 0.957 | 0.936 | 0.830 |
| LegalBench | ucc_v_common_law (rule-application) | 94 | 0.989 | 1.000 | 1.000 |
| LegalBench | mean of task accuracies | 1079 | 0.849 | 0.849 | 0.802 |
| Fragment cases | deadline cases | 87 | 0.862 | 0.874 | 0.851 |
| Fragment cases | flags cases | 110 | 1.000 | 1.000 | 1.000 |
| Fragment cases | all, bar 0.90 | 197 | 0.939 (pass) | 0.944 (pass) | 0.934 (pass) |
| Routing | manifest trigger | 141 | 0.894 | 0.872 | 0.879 |
| Routing | paraphrase | 72 | 1.000 | 1.000 | 1.000 |
| Routing | routing suite | 58 | 0.931 | 0.966 | 0.897 |
| Routing | all, bar 0.95 | 271 | 0.930 (below bar) | 0.926 (below bar) | 0.915 (below bar) |
<!-- results:end -->

Results of 2026-11-10. The LegalBench and fragment families were rerun in run
FIX-LEXBENCH-1 with the equal settings above: six batches submitted at 17:50Z, all ended by
18:05Z, with no errored requests. The routing results are from the batches of 16:45Z at
the entry-level settings. Earlier submissions remain recorded in `state/batches.json` as
superseded and are not reported. In the first, at the default thinking settings, thinking
used up the output bound and left 1,608 of 4,644 responses (34.6%) empty, between 0.5%
and 69.9% by entry and family. The LegalBench and fragment batches of 16:45Z, which gave
Opus 5.5 more output room than the other entries and printed each deadline category's kind
in the prompt, are superseded by the rerun. Their per-case records are kept in
`results/superseded/`.

Accuracy is the share of cases graded correct. A missing, empty, malformed or errored
response counts as incorrect, and so does a response in which no answer can be read under
the rules in [Grading](#grading). `results/summary.json` reports the number of such format
failures per task and model. The LegalBench row "mean of task accuracies" weights each
task equally; balanced accuracy per task is in `results/summary.json`. Per-case verdicts
are in `results/<family>/<model name>.jsonl`.

## Grading

The graders are deterministic and call no model.

- **LegalBench.** Every non-empty line of the response is read. Repeated answer cues (one to
  four words and a colon, such as "A:", "Label:", "FINAL ANSWER:" or "Governed by:") and
  edge punctuation are removed from each line. The answer is the last line that is then
  exactly a label of the task's label space. Failing that, a label of at least two
  characters that opens the first line and is followed by punctuation or the end of the
  line ("Yes, because ...") is read. A response with neither is a format failure.
- **Fragment cases.** The last JSON object in the response is the answer; a deadline case
  needs the category and the kind, and an intake case the exact set of flags.
- **Routing.** The first command-shaped token of the first line, with an optional leading
  slash, must equal the expected command.

**When the rules were settled.** The first commit (`f618b0b`) read only the first line of a
LegalBench response. After the first reported responses had been inspected, the head of
the first pull request (`224b4da`) also removed repeated cues, read the second line when
the first held only a cue, and read a label at the start of the first line; the fragment
grader began to take the last JSON object. Review XREVIEW-LEXBENCH-1 showed that the prefix
rule could read a wrong answer as right and that a label stated after reasoning was not
read. The current LegalBench rule was settled in commit `968dc8d`, before the rerun batches
were submitted, so the reported LegalBench and fragment responses were produced after the
rules were fixed. No rule was changed after the rerun responses were seen.

**Per-model effect of the rules** on the reported LegalBench responses (correct cases of
1,079, with the mean of task accuracies):

| Grading rule | claude-opus-5-5 | claude-sonnet-5-5 | claude-haiku-5-5 |
|---|---:|---:|---:|
| Strict: the whole response equals the label | 728 (0.699) | 657 (0.591) | 709 (0.661) |
| First commit `f618b0b` | 822 (0.782) | 695 (0.631) | 782 (0.735) |
| First pull request head `224b4da` | 898 (0.845) | 789 (0.715) | 845 (0.790) |
| Current rule (reported) | 902 (0.849) | 903 (0.849) | 856 (0.802) |

Most of the difference between strict match and the earlier rules comes from answer cues
repeated from the prompt, such as "FINAL ANSWER: NO" or "Governed by: UCC". The difference
between the `224b4da` rule and the current rule comes from responses that give a short
justification and then the label on a last line: 114 for Sonnet, 12 for Haiku and 4 for
Opus. Two Haiku responses state one label and then revise it; the last label is read,
which makes one correct and one incorrect. The order of the models therefore depends on
the rule. Under either earlier rule Sonnet ranks last. Under the current rule, Opus and
Sonnet are level (902 and 903 correct). One Opus response begins with a zero-width space
before "A: Yes" (`lb-proa-0009`). Its cue is therefore not removed, and the response counts
as a format failure although its label is correct. The rule was left unchanged, because
the response was seen only after the rerun.

## Pass bars

[graders/pass_bar.yaml](graders/pass_bar.yaml) sets a bar per family: routing at or above
0.95 and fragment cases at or above 0.90. LegalBench is reported per task without a bar.
The MHSB Stage 11 pass bar for the Platform Plugins skills is applied by that program to
LexBench results and is not defined here.

## How to run

```bash
uv sync                                    # Python 3.12, pinned dependencies (uv.lock)
uv run lexbench models                     # validate the registry, verify identifiers
uv run lexbench build                      # materialise data/ and data/MANIFEST.json (--refresh renews times)
uv run lexbench estimate                   # results/estimate.json; submits nothing
uv run lexbench run --family all --model claude-haiku-5-5
uv run lexbench poll                       # record batch status; download and grade ended batches
uv run lexbench grade                      # re-grade recorded responses
uv run lexbench report                     # results/summary.json and the table above
uv run pytest && uv run ruff check . && uv run mypy
```

Credentials are read from the variable each entry names in `auth`. The `mock` entry needs
no credential and runs every family end to end; its `hash` mode chooses among several answer
options for every family and is not an oracle.

The CLI sets `HF_HOME` (the datasets cache) and `TMPDIR` to `.lexbench-cache/hf` and
`.lexbench-cache/tmp` in the repository when they are not already set, and the test suite
places its temporary directories under `.lexbench-cache/pytest`, so that nothing is written
outside the repository. `uv` keeps its own cache; set `UV_CACHE_DIR` to keep it inside the
workspace as well.

## Licenses and attribution

LexBench is licensed under the Apache License 2.0, with two exceptions set out in
[NOTICE.md](NOTICE.md) and at the head of [LICENSE](LICENSE).

- **MHSB material.** `sources/mhsb/`, `data/fragments/`, `data/routing/` and the results
  derived from them are MHSB Solutions material, published here by its owner for
  evaluation under the terms of `LICENSE-SOURCE-AVAILABLE.md` in MHSBai/platform-plugins.
  They are not licensed under Apache-2.0. The fragment and routing case data is synthetic.
- **LegalBench.** The LegalBench family uses tasks from LegalBench (Guha et al. 2023,
  arXiv:2308.11462), https://github.com/HazyResearch/legalbench, under each task's CC BY 4.0
  license (https://creativecommons.org/licenses/by/4.0/). The evidence for each license is
  in data/legalbench/LICENSES.md, and NOTICE.md gives the attribution, the task sources,
  the citations two task READMEs request, and the changes made. The upstream gold labels in
  `results/legalbench/` remain under CC BY 4.0.

[counsel review] The carve-out of the MHSB material from the Apache-2.0 grant, and the
Apache-2.0 license for the LexBench code, are items for Richard Berman to confirm.
