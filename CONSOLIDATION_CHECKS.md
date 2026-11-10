# Consolidation checks — 7 November 2026

Active project: `/Users/amitoj/Developer/AITutor`.
Desktop access: `/Users/amitoj/Desktop/ChatBotTutorAI/AITutor` (same files).

## Preservation

117 unique files added with SHA-256 copy verification.
149 source comparisons were identical. 39 conflicting versions were archived
while retaining the Developer implementation. 10 older experimental files were
archived rather than activated. Original Desktop contents, including the nested
checkout and its separate databases, remain in
`/Users/amitoj/Desktop/ChatBotTutorAI_ARCHIVE_20261107`.
The main conversation database was not merged with other database files.

## Passed

- 33 tests: local OCR, LoCoMo evaluation protocol, official-data runner protocol.
- Frontend TypeScript and Vite production build.
- Actual FastAPI requests with local Qwen and Nomic, in temporary storage:
  older-message recall beyond recent history; streaming recall across chats;
  user separation; 768-dimensional vectors; source update and index deletion sync.
- Combined launch command: API health and frontend HTTP response; both server
  process groups stopped afterward. Temporary test data removed.

Live evidence: `benchmark_outputs/live_semantic_verification.json`.
File inventory: `project_consolidation/merged.json`.

## Existing limits

Before consolidation, the broader legacy backend suite had 43 passing and 19
failing tests in the restricted execution environment. Several attempted local
network calls that the environment blocked; others target the older agent-based
response path. These tests have not been rewritten or declared passing.
The separate live verification above passed with local-server access enabled.

Combining folders does not activate older graph/rolling-summary experiments or
verify teammate MySQL/Neo4j integrations. Those are separate implementation tasks.
The new OCR component remains separate from the chat route.
