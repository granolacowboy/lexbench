# [draft for Richard] LexBench: a small, reproducible harness for legal-task evaluation

Most published comparisons of language models on legal work are hard to reproduce. The
prompts are unpublished, the samples are unstated, and the grading depends on a reader's
judgement. LexBench is an attempt to make one modest measurement reproducibly. The task
data is fixed by hash, graders are deterministic, the models are named in a configuration
file, and the spend is capped before anything is submitted. This post describes the harness
and its first results on three Claude models.

## What is measured

LexBench has three task families.

The first is a subset of LegalBench (Guha et al. 2023), the collaboratively built benchmark
of legal reasoning tasks. Twelve tasks were selected whose upstream license is CC BY 4.0,
spread across four reasoning types: issue spotting, rule application, interpretation and
rhetorical understanding. Each task uses its upstream prompt with upstream's few-shot
examples, and at most 100 test examples, giving 1,080 cases. Every task has a closed label
set, so grading is normalised exact match.

The second family applies practice-area fragments, the structured definitions behind the
MHSB practice packs, to synthetic cases. A deadline case describes an event and asks which
deadline category it belongs to and whether that category is statutory or set by the firm.
An intake case gives firm settings, the rule for each attorney-review flag and an intake
record, and asks which flags the record raises; the correct answer may be none. There are
197 cases across twelve practice areas, generated from a fixed seed, with invented names
and dates.

The third family is routing: given a user's phrase and the list of 24 installed commands,
name the one command that should handle it. The 271 phrases combine the trigger phrases of
the plugin catalogue, a routing suite of ambiguous phrases, and three paraphrases per
command written for LexBench.

## Configuration

The three models were claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5, each run
through the Message Batches API. Every task is a short classification, so each model ran at
its lowest thinking setting: thinking disabled on Haiku, no up-front thinking on Sonnet,
and low effort on Opus, which cannot turn thinking off. The results therefore describe the
models at those settings, not at their defaults.

## Results

On the LegalBench subset, the mean of task accuracies was 0.847 for Opus, 0.790 for Sonnet
and 0.763 for Haiku. Pooled over all 1,080 cases, the accuracies were 0.833, 0.792 and
0.762.

The spread across tasks is wider than the spread across models. All three models reached
0.990 on cuad_audit_rights, and each scored at or above 0.950 on overruling. Two of the
rhetorical tasks were difficult for all three. On function_of_decision_section, which
classifies a paragraph of a judicial opinion into one of seven roles, accuracy was 0.510,
0.560 and 0.450. On oral_argument_question_purpose, which classifies a judge's question at
oral argument into one of seven purposes, it was 0.470, 0.480 and 0.320. The largest gaps
between models were on rule application. On hearsay, Opus reached 0.904, against 0.702 for
Sonnet and 0.670 for Haiku. On telemarketing_sales_rule, Opus reached 0.957, against 0.596
for Sonnet and 0.723 for Haiku.

Part of Sonnet's lower score is a matter of format rather than reasoning. In 40 of its
1,080 LegalBench responses, Sonnet began explaining its reasoning and did not reach a label
within the output bound; 18 of these were on telemarketing_sales_rule. Opus gave 10
responses that could not be read as a label, six of them on proa, where it returned the
answer cue "A:" with nothing after it. Haiku gave one. The harness counts such responses as
incorrect, because the task asks for the label alone.

On the fragment cases, Opus and Sonnet answered all 197 correctly. Haiku answered 188
correctly (0.954): 85 of 87 deadline cases and 103 of 110 intake cases. All three models
cleared the pass bar of 0.90 for this family.

On routing, no model reached the pass bar of 0.95. Accuracy was 0.930 for Opus, 0.926 for
Sonnet and 0.915 for Haiku. Every model routed all 72 written paraphrases correctly. The
errors fell mainly on the catalogue's trigger phrases, where accuracy was 0.894, 0.872 and
0.879. Many of those triggers are fragments of a sentence, such as "run the" or "file
ready", that match inside a longer request but carry little meaning alone. That result
says as much about the trigger list as about the models, and it is the most actionable
finding for the plugin catalogue.

## Limits

These results cover twelve LegalBench tasks, not the benchmark as a whole, and some tasks
have fewer than 100 test examples. The fragment and routing cases are synthetic and test
whether a model applies stated definitions, not whether those definitions are legally
correct. Each model was run once, at one thinking setting, with one prompt per family. No
claim is made beyond these measured tasks.

## Reproducing the results

The harness is public at github.com/granolacowboy/lexbench. Models are entries in a YAML
registry, so a self-hosted model behind any OpenAI-compatible server is one entry, and a
new provider is one class. The LegalBench records are rebuilt from pinned upstream
revisions and checked against recorded hashes. Every batch submission is recorded with
its estimated cost.

LegalBench: Neel Guha et al., "LegalBench: A Collaboratively Built Benchmark for Measuring
Legal Reasoning in Large Language Models", 2023, arXiv:2308.11462.
