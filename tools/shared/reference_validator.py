from __future__ import annotations

import time

from tools.shared.validation_result import ValidatorResult
from tools.shared.utils import normalize_meta_value


def validate_transition(transition: str, artifacts: dict, config: dict) -> ValidatorResult:
    start = time.monotonic()
    result = ValidatorResult(validator="references")

    from_records: list[dict] = artifacts.get("from_records", [])
    to_records: list[dict] = artifacts.get("to_records", [])

    if transition == "10_to_20":
        valid_docs = {normalize_meta_value(r, "document_id") for r in from_records}
        valid_docs.discard("")
        for rec in to_records:
            result.checked += 1
            file = str(rec.get("__file", ""))
            doc_id = normalize_meta_value(rec, "document_id")
            if doc_id and doc_id not in valid_docs:
                result.add_message(identifier=doc_id, file=file, rule="reference_document", description="document reference unresolved", severity="FATAL")

    elif transition == "20_to_30":
        valid_pairs = {
            (normalize_meta_value(r, "document_id"), normalize_meta_value(r, "chapter_id"))
            for r in from_records
        }
        valid_pairs.discard(("", ""))
        for rec in to_records:
            result.checked += 1
            file = str(rec.get("__file", ""))
            pair = (normalize_meta_value(rec, "document_id"), normalize_meta_value(rec, "chapter_id"))
            if pair not in valid_pairs:
                result.add_message(identifier=f"{pair[0]}:{pair[1]}", file=file, rule="reference_chapter", description="chapter reference unresolved", severity="FATAL")

    elif transition == "30_to_40":
        valid_chunk_ids = {normalize_meta_value(r, "chunk_id") for r in from_records}
        valid_chunk_ids.discard("")
        for rec in to_records:
            result.checked += 1
            file = str(rec.get("__file", ""))
            chunk_id = normalize_meta_value(rec, "chunk_id")
            if chunk_id and chunk_id not in valid_chunk_ids:
                result.add_message(identifier=chunk_id, file=file, rule="reference_chunk", description="chunk reference unresolved", severity="FATAL")
            source_refs = normalize_meta_value(rec, "source_references")
            if not source_refs:
                result.add_message(identifier=chunk_id or "source_references", file=file, rule="reference_source", description="source references missing", severity="ERROR")

    elif transition == "40_to_50":
        valid_chunk_ids = {normalize_meta_value(r, "chunk_id") for r in from_records}
        valid_chunk_ids.discard("")
        valid_evidence_ids = {normalize_meta_value(r, "evidence_id") for r in from_records}
        valid_evidence_ids.discard("")

        embedded_chunk_ids: set[str] = set()
        embedded_evidence_ids: set[str] = set()

        for rec in to_records:
            result.checked += 1
            file = str(rec.get("__file", ""))
            chunk_id = normalize_meta_value(rec, "chunk_id")
            evidence_id = normalize_meta_value(rec, "evidence_id")

            if chunk_id and chunk_id not in valid_chunk_ids:
                result.add_message(identifier=chunk_id, file=file, rule="reference_chunk", description="chunk reference unresolved", severity="FATAL")
            if evidence_id and evidence_id not in valid_evidence_ids:
                result.add_message(identifier=evidence_id, file=file, rule="reference_evidence", description="evidence reference unresolved", severity="FATAL")

            if chunk_id:
                embedded_chunk_ids.add(chunk_id)
            if evidence_id:
                embedded_evidence_ids.add(evidence_id)

        missing_by_chunk = sorted(valid_chunk_ids - embedded_chunk_ids)
        for missing in missing_by_chunk:
            result.add_message(
                identifier=missing,
                file=str(artifacts.get("to_path", "")),
                rule="coverage_chunk",
                description="missing embedding for chunk from layer40",
                severity="ERROR",
            )

        missing_by_evidence = sorted(valid_evidence_ids - embedded_evidence_ids)
        for missing in missing_by_evidence:
            result.add_message(
                identifier=missing,
                file=str(artifacts.get("to_path", "")),
                rule="coverage_evidence",
                description="missing embedding for evidence from layer40",
                severity="ERROR",
            )

    result.duration = round(time.monotonic() - start, 6)
    return result
