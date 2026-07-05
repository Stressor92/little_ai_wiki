from __future__ import annotations

import time

from tools.shared.validation_result import ValidatorResult
from tools.shared.utils import normalize_meta_value


def validate_transition(transition: str, artifacts: dict, config: dict) -> ValidatorResult:
    start = time.monotonic()
    result = ValidatorResult(validator="lineage")

    from_records: list[dict] = artifacts.get("from_records", [])
    to_records: list[dict] = artifacts.get("to_records", [])

    from_doc_ids = {normalize_meta_value(r, "document_id") for r in from_records}
    from_doc_ids.discard("")

    seen_ids: set[str] = set()

    for rec in to_records:
        result.checked += 1
        file = str(rec.get("__file", ""))

        if transition == "10_to_20":
            source_id = normalize_meta_value(rec, "source_id")
            document_id = normalize_meta_value(rec, "document_id")
            chapter_id = normalize_meta_value(rec, "chapter_id")
            if not source_id:
                result.add_message(identifier="source_id", file=file, rule="lineage", description="missing source_id", severity="ERROR")
            if not document_id:
                result.add_message(identifier="document_id", file=file, rule="lineage", description="missing document_id", severity="ERROR")
            if not chapter_id:
                result.add_message(identifier="chapter_id", file=file, rule="lineage", description="missing chapter_id", severity="ERROR")
            if document_id and document_id not in from_doc_ids:
                result.add_message(identifier=document_id, file=file, rule="lineage", description="document_id not found in layer10", severity="ERROR")
            if chapter_id:
                key = f"{document_id}:{chapter_id}"
                if key in seen_ids:
                    result.add_message(identifier=key, file=file, rule="lineage", description="duplicate chapter_id within document", severity="ERROR")
                seen_ids.add(key)

        elif transition == "20_to_30":
            document_id = normalize_meta_value(rec, "document_id")
            chapter_id = normalize_meta_value(rec, "chapter_id")
            chunk_id = normalize_meta_value(rec, "chunk_id")
            if not document_id:
                result.add_message(identifier="document_id", file=file, rule="lineage", description="missing document_id", severity="ERROR")
            if not chapter_id:
                result.add_message(identifier="chapter_id", file=file, rule="lineage", description="missing chapter_id", severity="ERROR")
            if not chunk_id:
                result.add_message(identifier="chunk_id", file=file, rule="lineage", description="missing chunk_id", severity="ERROR")
            if chunk_id:
                if chunk_id in seen_ids:
                    result.add_message(identifier=chunk_id, file=file, rule="lineage", description="duplicate chunk_id", severity="ERROR")
                seen_ids.add(chunk_id)

        elif transition == "30_to_40":
            evidence_id = normalize_meta_value(rec, "evidence_id")
            chunk_id = normalize_meta_value(rec, "chunk_id")
            if not evidence_id:
                result.add_message(identifier="evidence_id", file=file, rule="lineage", description="missing evidence_id", severity="ERROR")
            if not chunk_id:
                result.add_message(identifier="chunk_id", file=file, rule="lineage", description="missing chunk_id", severity="ERROR")
            if evidence_id:
                if evidence_id in seen_ids:
                    result.add_message(identifier=evidence_id, file=file, rule="lineage", description="duplicate evidence_id", severity="ERROR")
                seen_ids.add(evidence_id)

        elif transition == "40_to_50":
            embedding_id = normalize_meta_value(rec, "embedding_id")
            evidence_id = normalize_meta_value(rec, "evidence_id")
            chunk_id = normalize_meta_value(rec, "chunk_id")
            if not embedding_id:
                result.add_message(identifier="embedding_id", file=file, rule="lineage", description="missing embedding_id", severity="ERROR")
            if not evidence_id:
                result.add_message(identifier="evidence_id", file=file, rule="lineage", description="missing evidence_id", severity="ERROR")
            if not chunk_id:
                result.add_message(identifier="chunk_id", file=file, rule="lineage", description="missing chunk_id", severity="ERROR")
            if embedding_id:
                if embedding_id in seen_ids:
                    result.add_message(identifier=embedding_id, file=file, rule="lineage", description="duplicate embedding_id", severity="ERROR")
                seen_ids.add(embedding_id)

    result.duration = round(time.monotonic() - start, 6)
    return result
