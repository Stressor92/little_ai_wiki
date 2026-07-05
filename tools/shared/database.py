"""
Datenbank-Layer: SQLite mit erweitertem Schema für strukturierten Index.

Schema für 10_index_medical:
  id              – auto-generierte Ganzzahl
  ...             – Metadaten
  key_finding     – extrahierter Hauptbefund
  risk            – extrahiertes Risiko
  population      – Zielpopulation
  limitations     – erkannte Limitierungen
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

log = logging.getLogger(__name__)

# Autoincrement-Startpunkt für lesbare IDs (100000001, 100000002, ...)
ID_OFFSET = 100_000_000


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key      TEXT NOT NULL,        -- "pubmed:12345678"
                source          TEXT NOT NULL,        -- pubmed|pmc|doaj|plos
                external_id     TEXT NOT NULL,
                title           TEXT,
                abstract        TEXT,
                authors         TEXT,                 -- JSON array
                journal         TEXT,
                year            INTEGER,
                doi             TEXT,
                pmid            TEXT,
                pmcid           TEXT,
                url             TEXT,
                fulltext_url    TEXT,
                pdf_url         TEXT,
                is_open_access  INTEGER DEFAULT 0,
                study_type      TEXT,
                topics          TEXT,                 -- JSON array

                -- Strukturierter Index (10_index_medical)
                population      TEXT,
                key_finding     TEXT,
                risk            TEXT,
                limitations     TEXT,

                relevance_score REAL DEFAULT 0.0,
                downloaded      INTEGER DEFAULT 0,
                download_path   TEXT,
                fetched_at      TEXT,
                created_at      TEXT DEFAULT (datetime('now')),

                UNIQUE(source_key)
            );

            CREATE TABLE IF NOT EXISTS search_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT,
                topic        TEXT,
                query        TEXT,
                result_count INTEGER,
                searched_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_topic   ON papers(topics);
            CREATE INDEX IF NOT EXISTS idx_score   ON papers(relevance_score DESC);
            CREATE INDEX IF NOT EXISTS idx_source  ON papers(source);
            CREATE INDEX IF NOT EXISTS idx_year    ON papers(year DESC);
        """)
    log.info(f"DB initialisiert: {db_path}")


@contextmanager
def get_conn(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_paper(db_path: Path, paper: Dict[str, Any]) -> bool:
    """Fügt Paper ein oder aktualisiert Score. Gibt True zurück wenn neu."""
    source_key = f"{paper['source']}:{paper['external_id']}"
    paper["source_key"] = source_key

    # Serialisieren
    for field in ("authors", "topics"):
        if field in paper and isinstance(paper[field], list):
            paper[field] = json.dumps(paper[field], ensure_ascii=False)

    with get_conn(db_path) as conn:
        existing = conn.execute(
            "SELECT id, relevance_score FROM papers WHERE source_key = ?",
            (source_key,),
        ).fetchone()

        if existing:
            if paper.get("relevance_score", 0) > existing["relevance_score"]:
                conn.execute(
                    """UPDATE papers SET
                        relevance_score = ?,
                        topics          = COALESCE(?, topics),
                        key_finding     = COALESCE(?, key_finding),
                        risk            = COALESCE(?, risk),
                        population      = COALESCE(?, population),
                        limitations     = COALESCE(?, limitations),
                        fetched_at      = ?
                    WHERE source_key = ?""",
                    (
                        paper.get("relevance_score"),
                        paper.get("topics"),
                        paper.get("key_finding"),
                        paper.get("risk"),
                        paper.get("population"),
                        paper.get("limitations"),
                        datetime.now().isoformat(),
                        source_key,
                    ),
                )
            return False

        cols = [c for c in paper if c != "id"]
        placeholders = ", ".join(["?"] * len(cols))
        conn.execute(
            f"INSERT INTO papers ({', '.join(cols)}) VALUES ({placeholders})",
            [paper[c] for c in cols],
        )
        return True


def mark_downloaded(db_path: Path, source_key: str, path: str):
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE papers SET downloaded=1, download_path=? WHERE source_key=?",
            (path, source_key),
        )


def log_search(db_path: Path, source: str, topic: str, query: str, count: int):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO search_log (source, topic, query, result_count) VALUES (?,?,?,?)",
            (source, topic, query, count),
        )


def get_papers_for_topic(
    db_path: Path,
    topic: str,
    min_score: float = 0.0,
    limit: int = 200,
) -> List[Dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM papers
               WHERE topics LIKE ?
               AND relevance_score >= ?
               ORDER BY relevance_score DESC
               LIMIT ?""",
            (f'%"{topic}"%', min_score, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_papers(
    db_path: Path,
    min_score: float = 0.0,
    only_downloaded: bool = False,
) -> List[Dict]:
    with get_conn(db_path) as conn:
        q = "SELECT * FROM papers WHERE relevance_score >= ?"
        params = [min_score]
        if only_downloaded:
            q += " AND downloaded = 1"
        q += " ORDER BY relevance_score DESC"
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_stats(db_path: Path) -> Dict:
    with get_conn(db_path) as conn:
        total      = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        downloaded = conn.execute("SELECT COUNT(*) FROM papers WHERE downloaded=1").fetchone()[0]
        oa         = conn.execute("SELECT COUNT(*) FROM papers WHERE is_open_access=1").fetchone()[0]
        by_source  = dict(conn.execute("SELECT source, COUNT(*) FROM papers GROUP BY source").fetchall())
        top5       = conn.execute(
            "SELECT title, relevance_score, source FROM papers ORDER BY relevance_score DESC LIMIT 5"
        ).fetchall()
    return {
        "total": total,
        "downloaded": downloaded,
        "open_access": oa,
        "by_source": by_source,
        "top_papers": [dict(r) for r in top5],
    }
