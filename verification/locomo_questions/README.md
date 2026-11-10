# Questions behind the reported benchmark

- `Questions_Used.md`: every selected question, reference and per-mode mean score/time.
- `Recorded_Answers.csv`: all 588 actual Qwen predictions and recorded measurements.
- `questions_and_results.json`: the same questions with individual trials and source-selection traces.
- `source_manifest.json`: original settings and source hashes.
- `show_questions.py`: terminal viewer, using saved output only.

From the project root:

```bash
.venv/bin/python -B verification/locomo_questions/show_questions.py
```

For one question and all 12 recorded answers:

```bash
.venv/bin/python -B verification/locomo_questions/show_questions.py --question 1 --answers
```

Numbers 1-49 are display numbers, not upstream QA indices. The source conversation ID and original zero-based QA index remain attached to each record. F1 is word overlap, not factual accuracy. Category 5 uses the upstream abstention phrase rule. No benchmark was rerun and no learner chats were modified to produce this export.
