# [draft for Richard Berman] LexBench: a small, reproducible harness for legal-task evaluation

Most published comparisons of language models on legal work are hard to reproduce. The
prompts are unpublished, the samples are unstated, and the grading depends on a reader's
judgement. LexBench is an attempt to make one modest measurement reproducibly. The task
data is fixed by hash, the graders are deterministic, and the models are named in a
configuration file. Before each submission it makes, the harness adds the submission's
estimated cost to the estimates already recorded and refuses any submission that would
take the total above a cap of USD 60. Two small diagnostic requests made during setup did
not go through the harness and were recorded by hand. This post describes the harness and
its first results on three Claude models.

## What is measured

LexBench has three task families.

The first is a subset of LegalBench (Guha et al. 2023), the collaboratively built benchmark
of legal reasoning tasks. Twelve tasks were selected whose upstream license is CC BY 4.0,
spread across four reasoning types: issue spotting, rule application, interpretation and
rhetorical understanding. Each task uses its upstream prompt with upstream's few-shot
examples, and at most 100 test examples. One sampled case repeats the last example of its
prompt and is excluded, which leaves 1,079 cases. Every task has a closed label set.

The second family applies practice-area fragments, the structured definitions behind the
MHSB practice packs, to synthetic cases. A deadline case lists the fragment's deadline
categories by name, describes an event, and asks which category it belongs to and whether
that category is statutory (a period fixed by statute or court rule) or set by the firm (a
date the firm sets, or enters from a notice, order, contract or document). The prompt does
not say which kind each category is, so the kind must be judged. An intake case gives firm
settings, the rule for each attorney-review flag and an intake record, and asks which
flags the record raises; the correct answer may be none. There are 197 cases across
twelve practice areas, generated from a fixed seed, with invented names and dates.

The third family is routing: given a user's phrase and the list of 24 installed commands,
name the one command that should handle it. The 271 phrases combine the trigger phrases of
the plugin catalogue, a routing suite of ambiguous phrases, and three paraphrases per
command written for LexBench.

## Configuration

The three models were claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5, each run
through the Message Batches API.

For LegalBench and the fragment cases, all three models ran with the same settings:
adaptive thinking at low effort, the one thinking setting all three accept, and the same
output bound per request, 1,048 tokens for LegalBench and 1,624 for fragment cases. That
leaves room for a label and a short justification, and no response reached the bound. The
median LegalBench response was 7 tokens for Opus and 5 for Sonnet and Haiku.

Routing was measured earlier, at each model's lowest thinking setting: low effort on Opus,
which cannot turn thinking off, no up-front thinking on Sonnet, and thinking disabled on
Haiku. The output bounds were unequal: 1,044 tokens for Opus and 20 for Sonnet and Haiku.
The routing comparison should be read with that difference in mind.

No temperature was set. The Claude 5.5 models reject the parameter, so each ran at the
provider's fixed default sampling, and a repeated run need not give identical responses.

## Grading

LegalBench responses are graded by label match over the whole response. Answer cues
repeated from the prompt, such as "A:" or "Governed by:", are removed from each line, and
the last line that is then exactly one of the task's labels is the answer. Failing that,
a label of at least two characters that opens the response and is followed by punctuation
or the end of the line is read ("Yes, because ..."). A response from which no label can be read counts as
incorrect. Fragment responses are graded on the last JSON object in the response, and
routing responses on the first command name.

These rules were not fixed in advance of every measurement. The first version read only
the first line of a LegalBench response. It was loosened after the first responses had
been inspected, and changed again after an independent review found that the loosened rule
could read a wrong answer as right and ignored a label stated after a justification. The
current rule was fixed before the responses reported here were requested, and was not
changed after they were seen. The rule matters. On the reported responses, a strict
reading that accepts only a response consisting of the label alone gives 728, 657 and 709
correct of 1,079 for Opus, Sonnet and Haiku. The first rule gives 822, 695 and 782, the
loosened rule 898, 789 and 845, and the current rule 902, 903 and 856. Under either
earlier rule Sonnet ranks last; under the current rule it is level with Opus. The
difference comes mainly from Sonnet, which in 114 cases gave a short justification before
its label.

## Results

On the LegalBench subset, the mean of task accuracies was 0.849 for Opus, 0.849 for Sonnet
and 0.802 for Haiku. Pooled over all 1,079 cases, the accuracies were 0.836, 0.837 and
0.793.

The spread across tasks is wider than the spread across models. All three models reached
at least 0.990 on cuad_audit_rights and 1.000 on diversity_1, and each scored at or above
0.950 on overruling. Two of the rhetorical tasks were difficult for all three. On
function_of_decision_section, which classifies a paragraph of a judicial opinion into one
of seven roles, accuracy was 0.556, 0.576 and 0.455. On oral_argument_question_purpose,
which classifies a judge's question at oral argument into one of seven purposes, it was
0.460, 0.520 and 0.350. The largest gaps between models were on interpretation and on one
rule-application task. On insurance_policy_interpretation, Opus reached 0.660, against
0.590 for Sonnet and 0.540 for Haiku. On telemarketing_sales_rule, Opus reached 0.957 and
Sonnet 0.936, against 0.830 for Haiku.

Equal output room changed the comparison. In the first reported run, Sonnet and Haiku had
24 output tokens per LegalBench case while Opus had 1,048, and Sonnet scored 0.702 on
hearsay and 0.596 on telemarketing_sales_rule. With equal room it scored 0.862 and 0.936.
Few responses now fail to give a label: 5 for Opus, all on proa, 2 for Sonnet and none for
Haiku. Four of the Opus failures are the answer cue "A:" with nothing after it. The fifth
begins with an invisible zero-width character before "A: Yes", which the grader does not
read, although the label is correct.

On the fragment cases, Opus answered 185 of 197 correctly (0.939), Sonnet 186 (0.944) and
Haiku 184 (0.934). All three cleared the pass bar of 0.90. Every model identified the
attorney-review flags correctly in all 110 intake cases. The errors were on the deadline
cases: 75, 76 and 74 of 87 correct. Nearly all were the kind, not the category. Six
categories account for 35 of the 36 errors. Each follows a convention of its fragment:
two limitation-period categories, which the firm records itself, and assumed-name filings
are marked as set by the firm, while answer deadlines and appeal windows entered from the
docket, and response windows on agency notices, are marked statutory. When each category's
kind was printed in the
prompt, as in the first run, Opus and Sonnet answered every deadline case correctly. The
result therefore says as much about how clearly the fragments define their kinds as about
the models.

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
correct. Each model was run once per family, at one thinking setting, with one prompt per
family and the provider's default sampling. The grading rules were revised twice, and
the comparison between Opus and Sonnet on LegalBench depends on the rule used. No claim
is made beyond these measured tasks.

## Reproducing the results

The harness is public at github.com/granolacowboy/lexbench. Models are entries in a YAML
registry, so a self-hosted model behind any OpenAI-compatible server is one entry, and a
new provider is one class. The LegalBench records are rebuilt from pinned upstream
revisions and checked against recorded hashes. Every batch submission is recorded with
its estimated cost, and the per-case verdicts, including those of superseded runs, are
published with the code.

LegalBench: Neel Guha et al., "LegalBench: A Collaboratively Built Benchmark for Measuring
Legal Reasoning in Large Language Models", 2023, arXiv:2308.11462.
