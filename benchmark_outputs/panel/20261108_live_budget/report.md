# Memory configuration comparison

Current context builder; selected official LoCoMo questions; declared modes; repeated local generation

| Mode | Completed | Answer F1 1–4 | Abstention 5 | Generation ms | Context ms | Input tokens |
|---|---:|---:|---:|---:|---:|---:|
| buffer | 147/147 | 0.0053 | 0.9000 | 1411.7189 | 70.1723 | 867.6327 |
| summary | 147/147 | 0.0098 | 0.8333 | 2370.2483 | 97.3501 | 1069.5102 |
| vector | 147/147 | 0.1637 | 0.6000 | 4671.8177 | 740.0657 | 1231.5102 |
| graph | 147/147 | 0.0247 | 0.6000 | 4323.0358 | 426.9801 | 1009.3878 |

All modes use the same questions, sources, budget and decoding settings. No answer keys or predictions enter test memory.
The summary strategy is extractive and the graph extractor is rule-based. They are not full implementations of MemGPT, Mem0 or A-MEM.
The first available question per category is a deterministic subset, not a random sample. Category 5 uses the upstream phrase rule, not an LLM judge.
Generation and context timings exclude corpus ingestion. Local HTTP timing is not a cloud API measurement.
This evaluates current context code directly. HTTP save/delete/image integration is checked separately.
Every failure remains in predictions.jsonl. Intervals are clustered by conversation; repeated outputs are not independent new questions.
