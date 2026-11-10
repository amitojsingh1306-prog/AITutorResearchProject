# Memory Research, Architecture, and Evaluation Plan

## Research Goal

The tutor must remember learner goals, misconceptions, preferences, and completed topics across sessions. The research question is:

> Which memory strategy best supports a persistent AI tutor: conversation buffer, rolling summary, ChromaDB vector memory, Neo4j graph memory, or a hybrid of ChromaDB and Neo4j?

For this project:

- Vector DB is always ChromaDB.
- Graph DB is always Neo4j.
- Conversation buffer and rolling summary are non-persistent baselines.

## Literature Review

MemGPT frames long-running assistants as systems that need explicit memory management because the language model context window is limited. It separates active context from external memory and uses memory operations to decide what should remain visible to the model. This motivates our split between working memory and long-term memory. Source: https://arxiv.org/abs/2310.08560

Generative Agents introduced an agent architecture with memory stream, reflection, and planning. It shows why raw logs alone are not enough: agents need retrieval and higher-level reflections over stored experiences. This supports our use of structured learner memories instead of simply replaying full chat history. Source: https://arxiv.org/abs/2304.03442

LoCoMo evaluates very long-term conversational memory across long dialogues and question-answering tasks. It is relevant because our tutor must answer questions about previous sessions, completed topics, and learner state. Source: https://arxiv.org/abs/2402.17753

LongMemEval evaluates long-term assistant memory using information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. These categories map closely to tutor memory requirements: remembering goals, updating misconceptions, recognizing completed topics, and saying when no saved memory exists. Source: https://arxiv.org/abs/2410.10813

Neo4j is used as the graph database because graph memory needs explicit relationships among learners, goals, topics, misconceptions, and completed work. ChromaDB is used as the vector database because semantic retrieval is better suited to approximate matching of free-text learner memories.

## Implemented Architecture

### 1. Conversation Buffer

File: `backend/memory/working_memory.py`

The buffer keeps the latest useful conversation messages and removes low-signal user turns such as greetings. It is fast and simple but does not persist learner state across sessions.

Storage:

- Recent in-process chat context only
- No ChromaDB
- No Neo4j

Strengths:

- Lowest latency
- Easy baseline
- Good for immediate follow-up questions

Weaknesses:

- Forgets older sessions
- Cannot reliably remember goals, misconceptions, or completed topics

### 2. Rolling Summary

File: `backend/memory/working_memory.py`

Rolling summary compresses older turns into one synthetic summary message and appends the newest raw turns. This reduces prompt length while keeping some older context.

Storage:

- Summary text in active prompt context
- No ChromaDB by default
- No Neo4j by default

Strengths:

- Better long-chat continuity than buffer
- Lower prompt cost than full history

Weaknesses:

- Summary can lose details
- Mistakes in summary affect later answers
- Not a true cross-session memory unless persisted separately

### 3. Vector Memory With ChromaDB

Files:

- `backend/database/chroma_repository.py`
- `backend/memory/memory_store.py`
- `backend/memory/retrieval.py`
- `backend/memory/memory_manager.py`

The system stores durable learner memories in ChromaDB. Each memory is a structured student memory object containing topic, concepts, difficulty, progress, facts, tags, and timestamp. Retrieval combines semantic score, lexical overlap, importance, recency, and type filtering.

Storage:

- ChromaDB collection: `memories`
- ChromaDB collection: `learner_profiles`

Strengths:

- Good for semantic matching
- Handles natural-language queries
- Works well for approximate recall

Weaknesses:

- Does not explicitly model relationships
- May retrieve semantically similar but structurally wrong memories
- Harder to answer relation questions such as prerequisite paths

### 4. Graph Memory With Neo4j

Files:

- `backend/memory/memory_store.py`
- `backend/memory/retrieval.py`

Neo4j graph memory stores connected learner facts:

```text
(:Learner)-[:HAS_MEMORY]->(:Memory)-[:ABOUT_TOPIC]->(:Topic)
```

Memory nodes are additionally labeled by type:

- `GoalMemory`
- `MisconceptionMemory`
- `CompletedTopicMemory`
- `KnowledgeStateMemory`

Storage:

- Neo4j learner nodes
- Neo4j memory nodes
- Neo4j topic nodes
- Relationship edges between learners, memories, and topics

Strengths:

- Strong for structured learner modeling
- Can connect goals, misconceptions, completed topics, and topic dependencies
- Better for relation-heavy questions

Weaknesses:

- Requires Neo4j server
- More setup than ChromaDB
- Needs careful schema and graph queries

### 5. Hybrid Memory

Hybrid mode writes durable memories to both ChromaDB and Neo4j. Retrieval combines ChromaDB vector retrieval and Neo4j graph retrieval.

Storage:

- ChromaDB for semantic similarity
- Neo4j for structured relationships

Strengths:

- Best expected recall
- Supports both fuzzy semantic questions and structured graph questions

Weaknesses:

- Highest complexity
- Highest storage and operational cost
- Needs deduplication and weighting between stores

## Runtime Configuration

Set this in `.env`:

```dotenv
CHATBOT_MEMORY_STRATEGY=vector
```

Allowed values:

- `buffer`
- `rolling_summary`
- `vector`
- `graph`
- `hybrid`

For Neo4j graph or hybrid memory:

```dotenv
CHATBOT_NEO4J_URI=bolt://localhost:7687
CHATBOT_NEO4J_USERNAME=neo4j
CHATBOT_NEO4J_PASSWORD=change-me
CHATBOT_NEO4J_DATABASE=neo4j
```

## Evaluation Dataset

Create scripted multi-session learner conversations. Each scenario should include gold labels.

Example scenario:

Session 1:

- Learner goal: "I want to prepare for GATE CSE."
- Misconception: "I think recursion does not need a base case."
- Completed topic: "I completed binary search."
- Preference: "I prefer coding examples."

Session 2:

- Ask: "What am I preparing for?"
- Ask: "What mistake did I have in recursion?"
- Ask: "Which topic did I complete?"
- Ask: "Teach me the next topic in my style."

Gold labels:

- Goal: GATE CSE
- Misconception: recursion requires base case
- Completed topic: binary search
- Preference: coding examples

Run the same dataset across all memory strategies.

## Metrics

### 1. Memory Decision Accuracy

Measures whether the system correctly decides to store or ignore a learner turn.

```text
accuracy = (TP + TN) / (TP + TN + FP + FN)
```

Where:

- TP: useful memory correctly stored
- TN: non-memory correctly ignored
- FP: useless memory stored
- FN: useful memory missed

### 2. Precision, Recall, and F1

Precision measures memory cleanliness:

```text
precision = TP / (TP + FP)
```

Recall measures memory coverage:

```text
recall = TP / (TP + FN)
```

F1 balances both:

```text
F1 = 2 * precision * recall / (precision + recall)
```

### 3. Retrieval Recall@K

Measures whether the correct memory appears in the top K retrieved results.

```text
Recall@K = queries where correct memory is in top K / total queries
```

Use K values such as 1, 3, and 5.

### 4. Precision@K

Measures how many of the top K retrieved memories are relevant.

```text
Precision@K = relevant retrieved memories in top K / K
```

### 5. Mean Reciprocal Rank

Rewards systems that rank the correct memory higher.

```text
MRR = average(1 / rank of first correct memory)
```

### 6. Tutor Response Quality

Use a rubric from 1 to 5:

- Correctly uses remembered goal
- Correctly addresses misconception
- Avoids repeating completed topics
- Uses learner preference
- Does not invent unsupported memories

### 7. Latency

Measure average response or retrieval time:

```text
average_latency_ms = total_latency_ms / number_of_queries
```

Expected latency order:

```text
buffer < rolling_summary < ChromaDB vector < Neo4j graph < hybrid
```

## Expected Comparison Table

| Strategy | Cross-session memory | Semantic recall | Relationship reasoning | Setup complexity | Expected best use |
| --- | --- | --- | --- | --- | --- |
| Conversation buffer | No | Low | Low | Low | Immediate context |
| Rolling summary | Limited | Medium | Low | Low-medium | Long single chat |
| ChromaDB vector | Yes | High | Medium | Medium | Free-text memory recall |
| Neo4j graph | Yes | Medium | High | High | Goals, misconceptions, completed-topic relations |
| Hybrid | Yes | High | High | Highest | Full tutor personalization |

## Current Honest Status

Implemented:

- Conversation buffer
- Rolling summary
- ChromaDB vector memory
- Neo4j graph memory store/retriever
- Hybrid ChromaDB + Neo4j retrieval
- Metric utilities

Still needed before final report results:

- Run Neo4j locally for graph/hybrid experiments
- Build the labeled evaluation dataset
- Run all strategies on the same test cases
- Fill final result table with measured scores
