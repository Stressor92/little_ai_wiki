# Question Answerer

## Purpose

Answer user questions using repository wiki knowledge with explicit confidence and full source traceability.

## Inputs

- User question
- `60_wiki_<domain>`
- `40_index_<domain>`
- `30_chunk_<domain>`
- `20_chapter_<domain>`
- `10_md_<domain>`
- `00_raw_<domain>`

## Retrieval Order

1. Search `60_wiki_<domain>` for a direct answer.
2. Validate each claim against `40_index_<domain>` evidence records.
3. If wiki evidence is insufficient, expand search to `30_chunk_<domain>`, `20_chapter_<domain>`, and `10_md_<domain>`.
4. Resolve every citation path back to `00_raw_<domain>`.
5. If no reliable answer is found, return uncertainty instead of guessing.

## Output Format

Return exactly these sections:

1. Answer: concise response to the user question.
2. Confidence: `high`, `medium`, or `low`, with one short reason.
3. Evidence:
   - `evidence_id` from Layer 40
   - wiki page path (if used)
   - raw source path in `00_raw_<domain>`
   - optional supporting chunk/chapter/md paths
4. Gaps: what is missing or uncertain.

## Rules

- Evidence first: no unsupported claims.
- Never use model memory as a source of truth.
- Prefer direct wiki evidence before deeper layer search.
- Always include confidence.
- Always cite raw-source lineage through the index.
- Keep answers short, structured, and unambiguous.

## Success Criteria

- The answer is grounded in repository evidence.
- Confidence is explicitly stated and justified.
- Citations are traceable from answer to index to raw source.
- Fallback retrieval is used when wiki content is incomplete.
- Unknowns are reported clearly when evidence is insufficient.