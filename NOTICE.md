# Notice

LexBench is licensed under the Apache License, Version 2.0 (LICENSE).

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
- Each task used here is licensed CC BY 4.0 by its contributors; the license evidence per
  task, with the URL read and the time, is in data/legalbench/LICENSES.md. Individual tasks
  may also ask for a task-specific citation, given in each task README upstream.
- LexBench uses the upstream base prompts and test examples without modification. The
  records are materialised locally by `lexbench build` from pinned upstream revisions and are
  not redistributed in this repository. The task sample is a fixed random subset of at most
  100 test examples per task (seed 20261110).

## MHSB fragment and routing material

The fragment cases and routing phrases draw on trigger phrases, command names, intake
questions, deadline categories and attorney-review flags from the MHSB Platform Plugins
(MHSB Solutions). All case data is synthetic; every name, date and fact is invented.
