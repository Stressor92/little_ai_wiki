"""
Relevanz-Scoring: Bewertet Paper nach Nutzerprofil und Topic-Relevanz
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, List

from tools.shared.config import SCORING_CONFIG, USER_PROFILE

log = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year


def score_paper(paper: Dict[str, Any], topic_config: Dict) -> float:
    """
    Berechnet einen Relevanz-Score 0.0–1.0 für ein Paper.
    
    Faktoren:
    - Keyword-Matches in Titel/Abstract (topic-spezifisch)
    - Boost-Terms (Studientyp-Qualität)
    - Penalty-Terms (irrelevante Subpopulationen)
    - Publikationsjahr (Recency)
    - Open Access verfügbar
    """
    weights = SCORING_CONFIG["weights"]
    text = _get_text(paper)

    # Penalty: Artikel herausfiltern
    penalty = _check_penalties(text, topic_config.get("penalty_terms", []))
    if penalty:
        return 0.0

    scores = {}

    # 1. Keyword-Matching
    scores["keyword"] = _keyword_score(
        text, topic_config.get("keywords", [])
    ) * weights["keyword_match"]

    # 2. Boost-Term-Matching (Studienqualität etc.)
    scores["boost"] = _keyword_score(
        text, topic_config.get("boost_terms", []), boost=True
    ) * weights["boost_term_match"]

    # 3. Studientyp-Bonus
    scores["study_type"] = _study_type_score(text, paper.get("study_type", "")) * weights["study_type_bonus"]

    # 4. Aktualität
    scores["recency"] = _recency_score(paper.get("year")) * weights["recency_bonus"]

    # 5. Open Access
    scores["open_access"] = (1.0 if paper.get("is_open_access") else 0.0) * weights["open_access_bonus"]

    total = sum(scores.values())
    normalized = min(total / sum(weights.values()), 1.0)

    log.debug(
        f"Score {normalized:.2f} für '{paper.get('title', '')[:60]}' "
        f"({', '.join(f'{k}={v:.2f}' for k,v in scores.items())})"
    )
    return round(normalized, 3)


def detect_study_type(title: str, abstract: str) -> str:
    """Erkennt den Studientyp aus Titel/Abstract."""
    text = f"{title} {abstract}".lower()
    
    # Geordnet nach Priorität (spezifischste zuerst)
    patterns = [
        ("meta-analysis", r"\bmeta.analy"),
        ("systematic review", r"\bsystematic review\b"),
        ("randomized controlled trial", r"\brandomized controlled trial\b|\brct\b"),
        ("cohort study", r"\bcohort study\b|\bprospective cohort\b"),
        ("cross-sectional", r"\bcross.sectional\b"),
        ("case-control", r"\bcase.control\b"),
        ("review", r"\breview\b"),
        ("case report", r"\bcase report\b"),
    ]
    for study_type, pattern in patterns:
        if re.search(pattern, text):
            return study_type
    return "unknown"


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _get_text(paper: Dict) -> str:
    parts = [
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("journal", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _keyword_score(text: str, keywords: List[str], boost: bool = False) -> float:
    if not keywords:
        return 0.0
    matches = sum(1 for kw in keywords if kw.lower() in text)
    base_score = matches / len(keywords)
    if boost:
        # Boost-Terms geben mehr Score pro Match
        return min(base_score * 1.5, 1.0)
    return base_score


def _check_penalties(text: str, penalty_terms: List[str]) -> bool:
    """Gibt True zurück wenn Penalty-Term gefunden (Paper ausschließen)."""
    for term in penalty_terms:
        if term.lower() in text:
            # Nur penalisieren wenn kein gegenläufiges Signal
            # (z.B. "adults" rettet Paper mit "children" im Abstract)
            if "adults" not in text and "adult" not in text:
                return True
    return False


def _study_type_score(text: str, detected_type: str = "") -> float:
    study_scores = SCORING_CONFIG["study_type_scores"]
    
    # Direkt erkannt
    if detected_type and detected_type in study_scores:
        return study_scores[detected_type]
    
    # Aus Text ableiten
    for study_type, score in sorted(study_scores.items(), key=lambda x: -x[1]):
        if study_type in text:
            return score
    return 0.3  # Default


def _recency_score(year: Any) -> float:
    if not year:
        return 0.3
    try:
        age = CURRENT_YEAR - int(year)
        decay = SCORING_CONFIG["recency_decay_years"]
        if age <= 2:
            return 1.0
        elif age <= decay:
            return 1.0 - (age / decay) * 0.5   # Lineare Abnahme auf 0.5
        else:
            return max(0.1, 0.5 - (age - decay) * 0.02)
    except (ValueError, TypeError):
        return 0.3


def filter_and_rank(
    papers: List[Dict],
    topic_config: Dict,
    min_score: float = 0.4,
    max_results: int = 20,
) -> List[Dict]:
    """Bewertet, filtert und sortiert eine Liste von Papers."""
    scored = []
    for paper in papers:
        paper["study_type"] = detect_study_type(
            paper.get("title", ""), paper.get("abstract", "")
        )
        paper["relevance_score"] = score_paper(paper, topic_config)
        if paper["relevance_score"] >= min_score:
            scored.append(paper)

    scored.sort(key=lambda p: p["relevance_score"], reverse=True)
    return scored[:max_results]
