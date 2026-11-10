# Official LoCoMo Data: Local Tutor Evaluation

## What Is Implemented

`scripts/run_official_locomo.py` loads the official public
`snap-research/locomo` QA dataset. It is separate from the older synthetic
`AITutor/scripts/run_locomo_benchmark.py` demonstration.

The runner imports the current local tutor's `SemanticChatMemory` and
`ChatService._prepare_context`, rather than inventing a second retrieval algorithm.
It runs Qwen and Nomic through the loopback LM Studio server. It does not send
inference requests to an external API. The public dataset and scorer were
downloaded from GitHub; their hashes are recorded for each experiment.

## Controlled Comparison

- Baseline: the application's context builder without semantic retrieval.
- Hybrid: the same context builder with local Nomic and Chroma retrieval.
- Both use identical model, sampling settings, answer instruction and input budget.
- The application's existing chronological outline remains enabled in both modes
  when its trigger words occur. Therefore the baseline is not necessarily a strict
  last-N-message baseline.
- Conversation speakers are represented as historical user records, retaining
  speaker names, session dates and dialogue IDs.
- Supplied image captions are included as text; images are not downloaded.
- Only source dialogue is indexed. Benchmark QA, reference answers and generated
  predictions never enter test memory. Each run creates a fresh Chroma directory.
- The same source history is used for each independent question. No model-generated
  feedback is accumulated between questions.

## Scoring

The runner extracts and executes the reviewed QA scoring functions from the
downloaded upstream `task_eval/evaluation.py`, avoiding its unused heavyweight
BERTScore imports. The exact source file is retained and hashed.

- Categories 1-4 use the upstream normalization, Porter stemming and F1 rules.
- Category 1 splits comma-separated answers using the upstream partial-answer rule.
- Category 3 applies the upstream semicolon handling.
- Category 5 uses the upstream phrase-based abstention rule, not semantic judging.

The aggregate is a mean upstream QA score, not a calibrated probability or
classification accuracy. Category scores must be shown alongside the aggregate.
Retrieval cosine is not an answer score. Evidence-ID precision/recall and latency
are additional diagnostics, not replacements for the upstream answer metric.
Evidence-ID coverage can overestimate support if a selected excerpt omits the
relevant part of its source message.

This is an evaluation of the local tutor on official data, not an exact
reproduction of the paper's models, prompts, or published results. A subset run
must be labelled as a subset, not a full LoCoMo result or leaderboard score.

## Run

Use the installed environment that contains the live application's dependencies:

```bash
cd /Users/amitoj/Desktop/ChatBotTutorAI
/Users/amitoj/Developer/AITutor/.venv/bin/python scripts/test_official_locomo.py

# Up to fifty deterministic questions: first available question per category,
# per conversation. This dataset selects 49 because one category is absent
# from one conversation.
/Users/amitoj/Developer/AITutor/.venv/bin/python scripts/run_official_locomo.py \
  --questions-per-category 1 --max-tokens 128

# Full QA dataset: no conversation or category limits.
/Users/amitoj/Developer/AITutor/.venv/bin/python scripts/run_official_locomo.py \
  --max-tokens 128
```

LM Studio must serve the named Qwen and Nomic models. New environments also need
`nltk` and `regex` for the upstream scorer; no NLTK corpus download is required.
Model decoding seeds request reproducibility but do not guarantee identical
hardware-level results. Run repeated experiments before making statistical claims.

## Outputs

Each timestamped directory under `benchmark_outputs/official_locomo` contains:

- `manifest.json`: dataset/scorer/application hashes, settings and selected QA IDs.
- `predictions.jsonl`: each prediction, reference, score, usage, evidence and timings.
- `summary.json`: category aggregates, errors and completion status.
- `report.md`: readable comparison.
- `test_chroma`: isolated derived index; no live learner history is modified.

Model errors are logged explicitly and counted, not silently converted into valid
predictions. An interrupted experiment retains its checkpoint and is not marked
completed. Large full-dataset runs can take substantially longer than a subset.

## Source and Attribution

Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents*,
ACL 2024. Dataset and evaluation source:
https://github.com/snap-research/locomo

The upstream license is retained in `benchmark_data/locomo/LICENSE.txt`.
