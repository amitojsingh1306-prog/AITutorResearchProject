# Benchmarks and Hybrid Memory Plan

## Benchmark Map

| Aspect | Benchmark |
| --- | --- |
| Long-term memory | LoCoMo |
| Memory retention | LongMemEval |
| Retrieval performance | RAGBench |
| General chatbot ability | MT-Bench |
| Educational knowledge | MMLU |

## Hybrid Memory Plan

| Layer | Purpose |
| --- | --- |
| Buffer | Raw recent chat |
| Rolling summary | Old chat memory |
| Vector summary | Semantic search of past chats |
| Graph memory | Structured learner knowledge |

The current app stores chat history and uses Groq for live assistant responses.
The hybrid-memory package boundary exists, but buffer, rolling summary, vector
summary, and graph memory still need implementation before these benchmarks can
be run as real evaluations.
