# LexBench

LexBench is a model-agnostic harness for evaluating language models on legal tasks. It
builds three task families, sends them to any model listed in a YAML registry, grades the
responses with deterministic graders, and reports accuracy per task and family.

## Families

| Family | Source | Cases | Expected answer | Grader |
|---|---|---:|---|---|
| `legalbench` | 12 LegalBench tasks licensed CC BY 4.0 (Guha et al. 2023) | 1,080 | the task label | normalised exact match |
| `fragments` | synthetic intake and deadline cases from 12 MHSB practice-pack fragments | 197 | deadline category and kind, or the set of attorney-review flags | category and flag match |
| `routing` | MHSB trigger phrases, routing-suite phrases and written paraphrases | 271 | one command name | command match |

**LegalBench.** The tasks cover four reasoning types: issue spotting (`corporate_lobbying`),
rule application (`hearsay`, `diversity_1`, `personal_jurisdiction`, `ucc_v_common_law`,
`telemarketing_sales_rule`), interpretation (`proa`, `cuad_audit_rights`,
`insurance_policy_interpretation`) and rhetorical understanding
(`function_of_decision_section`, `oral_argument_question_purpose`, `overruling`). Each task
uses its upstream base prompt, whose in-context examples are upstream's few-shot
demonstrations from the train split. Each task contributes at most 100 test examples, drawn
as a fixed random sample (seed 20261110) when the split is larger. The license of every task
is read from its upstream README at build time and recorded in
[data/legalbench/LICENSES.md](data/legalbench/LICENSES.md).

**Fragment cases.** `lexbench/families/fragments.py` generates the cases from each fragment's
intake questions, deadline categories (kind `statutory` or `firm_set`) and attorney-review
flags, using the templates in `sources/fragments/templates.yaml`. The seed is 20261110. A
deadline case describes an event and asks for the category and its kind. An intake case
gives firm settings, the flag rules and an intake record, and asks for every flag whose
rule is met (possibly none). Sensitive intake questions are never shown. All names, dates
and facts are invented.

**Routing.** Each phrase is paired with the single command expected when all 24 commands are
installed. The prompt lists the commands with one-line descriptions written for LexBench.

`lexbench build` writes every family to `data/` and records counts and SHA-256 hashes in
`data/MANIFEST.json`. A run refuses data that does not match the manifest.

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
    max_tokens: 256                # output bound; each family sets a lower bound
    concurrency: 4                 # parallel requests for synchronous runs
    rate_limit_rpm: 50             # optional
    batch: true                    # use the provider's batch mode when it has one
```

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
    max_tokens: 256
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
request, and output tokens as the family's `max_tokens`, so the estimate is an upper bound.
Claude prices are checked against https://platform.claude.com/docs/en/about-claude/pricing
and the result is recorded with the fetch time. Before each submission, `lexbench run` adds
the submission's estimate to the estimates already recorded in `state/batches.json` and
`state/runs.json`. It refuses when the sum would exceed `limits.spend_cap_usd` (USD 60) or
when the estimate is stale. A batch holds at most 10,000 requests, and entries with zero
pricing count as zero. Each submission is recorded with its batch or run id, family, model
name, request count and estimated cost, so repeating `run` submits nothing new.

## Results

<!-- results:start -->
Results pending.
<!-- results:end -->

Accuracy is the share of cases graded correct. A missing, empty, malformed or errored
response counts as incorrect. The LegalBench row "mean of task accuracies" weights each
task equally; balanced accuracy per task is in `results/summary.json`. Per-case verdicts
are in `results/<family>/<model name>.jsonl`.

## Pass bars

[graders/pass_bar.yaml](graders/pass_bar.yaml) sets a bar per family: routing at or above
0.95 and fragment cases at or above 0.90. LegalBench is reported per task without a bar.
The MHSB Stage 11 pass bar for the Platform Plugins skills is applied by that program to
LexBench results and is not defined here.

## How to run

```bash
uv sync                                    # Python 3.12, pinned dependencies (uv.lock)
uv run lexbench models                     # validate the registry, verify identifiers
uv run lexbench build                      # materialise data/ and data/MANIFEST.json
uv run lexbench estimate                   # results/estimate.json; submits nothing
uv run lexbench run --family all --model claude-haiku-5-5
uv run lexbench poll                       # record batch status; download and grade ended batches
uv run lexbench grade                      # re-grade recorded responses
uv run lexbench report                     # results/summary.json and the table above
uv run pytest && uv run ruff check . && uv run mypy
```

Credentials are read from the variable each entry names in `auth`. The `mock` entry needs
no credential and runs every family end to end.

## Licenses and attribution

LexBench is licensed under the Apache License 2.0. The LegalBench family uses tasks from
LegalBench (Guha et al. 2023, arXiv:2308.11462), https://github.com/HazyResearch/legalbench,
under each task's CC BY 4.0 license. The evidence for each license is in
data/legalbench/LICENSES.md, and [NOTICE.md](NOTICE.md) gives the full attribution. The
fragment and routing families draw on trigger phrases, command names, intake questions,
deadline categories and attorney-review flags from the MHSB Platform Plugins. Their case
data is synthetic.
