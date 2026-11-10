# Evaluation Fixes: Local Tutor

## Scope

This harness tests output formatting and temporal grounding through the project's
real FastAPI chat route. It does not change the normal chatbot's system prompt,
replace earlier benchmark scores, or claim a new full LoCoMo result.

The two cases are deliberately selected regressions from earlier failures, not
an unbiased estimate of general answer accuracy. The reference answer is used
only after inference for scoring.

## Answer Boundaries

Tag-only prompting was tested and the small model ignored it. The supported
alternative is LM Studio's local schema-constrained output with separate
`answer` and `explanation` strings. The client calls only loopback LM Studio.

The parser does not search for reference words, split on question-specific
phrases, rewrite dates, or remove words to maximize a score. It validates the
declared output structure and reads the answer field. Invalid formats retain
the original output and an explicit parse failure status.

Both the complete raw response and extracted answer are saved. The upstream
LoCoMo scoring functions are run on both and the results have different names.
The answer-field score is a declared structured-answer protocol, not a silent
replacement for raw-response F1. Previous reports remain untouched.

## Temporal Grounding

The existing backend already includes source timestamps. A timestamp alone did
not prevent the model from confusing an utterance date with an event date.

The temporal evaluation mode:

1. Uses the timestamp of each selected source message, not the current date.
2. Keeps original text and adds calendar arithmetic beside yesterday/today/tomorrow.
3. Adds no reference-answer information and makes no new event claim.
4. Annotates only selected history and retrieved excerpts, not the entire corpus.
5. Leaves persisted source text and indexed embeddings unchanged.

For example, `yesterday` in a source message dated 8 May becomes
`yesterday [calendar date: 7 May 2023]`. This is a generic timedelta calculation.
It does not handle every temporal expression or resolve nested quotations.
Phrases such as "last Friday" or ambiguous time zones need additional work.

## Isolation

Every case runs in a separate child process with a new TemporaryDirectory under
`/private/tmp`. Only source dialogue is seeded; no QA or previous prediction is
indexed. The child exits before the parent removes its database, avoiding open
SQLite/Chroma handles during teardown. Failed workers and timeouts also exit
before cleanup. Reports and logs are saved outside the disposable directory.

The pytest fixture uses the same storage context. Tests cover cleanup after both
success and exception paths. No live learner chat history is touched.

## Comparison and Reproducibility

Default modes are raw, JSON answer, and JSON answer with temporal normalization.
All modes reserve the same amount of input capacity for evaluation instructions:
2,000 byte-bound context-selection units plus up to 800 reserved units, with a
checked total bound of 2,800. This conservative bound is not an exact tokenizer
count. Temperature is 0.1 and the output cap is 128 tokens.

The harness snapshots its runner and helper before launching workers, retaining
the exact code used by each run. Model inference is not guaranteed bit-identical.

## Run

```bash
cd /Users/amitoj/Developer/AITutor
.venv/bin/python -m pytest -q scripts/test_locomo_eval_protocol.py
.venv/bin/python scripts/validate_tutor_api.py
```

The default creates a unique report directory under `/private/tmp` and prints its
location. To keep reports in the local project, provide a new output directory:

```bash
.venv/bin/python scripts/validate_tutor_api.py \
  --output benchmark_outputs/my_new_regression_run
```

Do not reuse an existing output directory. Test databases are always temporary,
regardless of where the reports are saved.

## Inspect Results

`report.json` contains raw output, parsed answer, both F1 values, format status,
source-date annotations, context traces, and database-cleanup confirmation.
Per-case JSON and logs are retained. The source dataset and scorer hashes are
included in the report. Improvements on these two known cases must be followed
by a fresh, broader benchmark run before claiming general improvement.
