# Evaluation verdict

The scoring/protocol audit passed for all 588 predictions, with zero generation request errors in the offline benchmark. Each memory mode actually supplied its enabled evidence in all 147 requests. The independent live streaming test passed learner recall, correction and forgetting across active JSON, MySQL, Chroma and Neo4j stores.

Answer quality is still limited. Mean answer F1 on categories 1–4 was buffer 0.0053, summary 0.0098, vector 0.1637 and graph 0.0247. Vector scored highest on this selected subset, particularly on single-hop questions (0.2956). Its abstention score was 0.6000, below buffer's 0.9000. This does not establish a factual-accuracy percentage: F1 penalizes verbosity and synonyms, and a correct ISO-formatted date also received zero overlap credit. Manually inspected outputs include real wrong facts and incomplete multi-hop answers.

## Recommendations

- Use vector retrieval as the strongest measured baseline here; do not claim the graph or rolling summary implementations match published systems.
- Improve graph query/entity coverage and summary content selection, then retest on separately reserved questions.
- Treat unsupported answers and wrong entities separately from format/wording penalties.
- Address the non-streaming 60-second timeout before relying on that route for long answers. The actual frontend streaming check passed, but its first full response still took about 51 seconds.
- Expand beyond the fixed 49-question subset before making broad performance claims. Keep reference answers out of memory, preserve failures and report model/context settings.

## Responsible memory behavior

The current evidence supports local model inference, traceable source records, tested correction and deletion of active copies, and a terminal inspector. It does not certify privacy against every threat, deletion of external backups/provider logs, unrestricted cross-session retention beyond one-hour inactivity expiry, or complete image-lineage isolation.
