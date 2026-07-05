"""
Konfiguration: Suchbegriffe, Nutzerprofil, API-Einstellungen
"""

from pathlib import Path

# ─── Ausgabepfade ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
PAPERS_DIR = OUTPUT_DIR / "papers"
WIKI_DIR = OUTPUT_DIR / "wiki"
DB_PATH = OUTPUT_DIR / "papers.db"

# ─── Nutzerprofil (beeinflusst Relevanz-Scoring) ─────────────────────────────

USER_PROFILE = {
    "age": 35,
    "gender": "male",
    "occupation": "office worker",
    "activity": ["climbing", "sport", "fitness", "bouldering","hiking", "outdoors"],
    "location": "Germany",
    "lifestyle": "urban",
    "risk_factors": ["sedentary work", "screen time", "urban stress", "cognitive fatigue", "boreout", "burnout", "inflammation"],
    "interests": [
        "preventive health",
        "nutrition",
        "sleep optimization",
        "mental health",
        "ergonomics",
        "climbing performance",
        "resilience",
        "stoicism"
        "longevity",
        "Influence People",
        "optimizing healthspan",
        "Learning",
        "Habits",
        "Thinking",
        "Relationships",
        "Productivity",
        "Logotherapy",
        "Humanistic Psychology",
        "Behavioral Therapy",
        "forgetfulness",
        "Concentration",
        "autonomic nervous system",
        "vagus nerve",
        "stress adaptation"
        "circadian nutrition"
        "glucose stability"
        "Bayesian thinking"
        "probabilistic reasoning"
        "decision making under uncertainty"
        "identity-based habits"
        "finger strength periodization",
        "connective tissue adaptation",
        "metabolism"
    ],
}

# ─── Topics & Suchstrategien ─────────────────────────────────────────────────
# Jedes Topic hat:
#   - category: Oberkategorie fürs Wiki
#   - queries: Liste von Suchanfragen (werden alle ausgeführt, Duplikate dedupliziert)
#   - keywords: Für Relevanz-Scoring (Treffer erhöhen Score)
#   - boost_terms: Starke Relevanz-Signale (doppelt gewichtet)
#   - penalty_terms: Irrelevante Papers herausfiltern

TOPICS = {
    # ── PRÄVENTION ────────────────────────────────────────────────────────────
    "ernaehrung_allgemein": {
        "category": "Prävention/Ernährung",
        "label": "Ernährung Allgemein",
        "emoji": "🥗",
        "queries": [
            "healthy diet prevention chronic disease men 30-40",
            "Mediterranean diet cardiovascular risk reduction",
            "dietary patterns longevity epidemiology",
            "nutrition guidelines adults evidence-based",
        ],
        "keywords": ["diet", "nutrition", "healthy eating", "prevention", "chronic disease"],
        "boost_terms": ["randomized controlled trial", "meta-analysis", "systematic review", "men", "adults 30-40"],
        "penalty_terms": ["pediatric", "children", "infant", "elderly >70", "postmenopausal"],
    },
    "fasten": {
        "category": "Prävention/Ernährung",
        "label": "Fasten & Intervallfasten",
        "emoji": "⏱️",
        "queries": [
            "intermittent fasting health benefits men",
            "time-restricted eating metabolic health",
            "intermittent fasting weight management adults",
            "caloric restriction longevity mechanisms",
            "16:8 fasting protocol clinical trial",
        ],
        "keywords": ["fasting", "intermittent fasting", "time-restricted eating", "caloric restriction"],
        "boost_terms": ["meta-analysis", "randomized", "men", "adults", "metabolic"],
        "penalty_terms": ["children", "pediatric", "elderly", "eating disorder"],
    },
    "fleisch_und_ernaehrung": {
        "category": "Prävention/Ernährung",
        "label": "Fleisch & tierische Produkte",
        "emoji": "🥩",
        "queries": [
            "red meat consumption cancer risk men",
            "processed meat health effects systematic review",
            "plant-based diet health outcomes men",
            "meat consumption cardiovascular disease risk",
            "protein sources health comparison",
        ],
        "keywords": ["meat", "red meat", "processed meat", "plant-based", "protein"],
        "boost_terms": ["cohort study", "meta-analysis", "systematic review", "cancer risk", "cardiovascular"],
        "penalty_terms": ["animals", "livestock", "veterinary"],
    },
    "alkohol": {
        "category": "Prävention/Ernährung",
        "label": "Alkohol",
        "emoji": "🍺",
        "queries": [
            "alcohol consumption health risks moderate drinking",
            "alcohol cancer risk dose-response",
            "alcohol liver disease prevention",
            "alcohol sleep quality disruption",
            "low-risk drinking guidelines evidence",
        ],
        "keywords": ["alcohol", "drinking", "ethanol", "liver", "cancer risk"],
        "boost_terms": ["dose-response", "meta-analysis", "cohort", "men", "risk"],
        "penalty_terms": ["alcoholism treatment", "rehabilitation", "pediatric"],
    },
    "bewegung": {
        "category": "Prävention/Bewegung",
        "label": "Bewegung & Sport",
        "emoji": "🏃",
        "queries": [
            "physical activity prevention chronic disease adults",
            "exercise cardiovascular health benefits",
            "resistance training health outcomes men 30-40",
            "sedentary behavior health risks office workers",
            "exercise dose-response mortality risk",
            "HIIT high intensity interval training benefits",
        ],
        "keywords": ["exercise", "physical activity", "sport", "fitness", "training"],
        "boost_terms": ["meta-analysis", "randomized", "office workers", "sedentary", "adults"],
        "penalty_terms": ["pediatric", "children", "elderly", "rehabilitation"],
    },
    "klettern": {
        "category": "Prävention/Bewegung",
        "label": "Klettern & Verletzungsprävention",
        "emoji": "🧗",
        "queries": [
            "rock climbing injury prevention",
            "climbing training finger strength",
            "sport climbing overuse injury upper extremity",
            "climbing performance training load",
            "bouldering health benefits physical fitness",
        ],
        "keywords": ["climbing", "rock climbing", "bouldering", "finger", "upper extremity"],
        "boost_terms": ["injury prevention", "training", "overuse", "performance"],
        "penalty_terms": [],
    },
    "schlaf": {
        "category": "Prävention/Schlaf",
        "label": "Schlaf",
        "emoji": "😴",
        "queries": [
            "sleep duration health outcomes adults",
            "sleep quality cardiovascular risk",
            "sleep hygiene intervention evidence",
            "circadian rhythm disruption health effects",
            "insomnia CBT cognitive behavioral therapy",
            "sleep deprivation cognitive performance",
        ],
        "keywords": ["sleep", "insomnia", "circadian", "sleep duration", "sleep quality"],
        "boost_terms": ["meta-analysis", "randomized", "adults", "men", "cognitive"],
        "penalty_terms": ["pediatric", "neonatal", "children", "apnea treatment"],
    },
    # ── PSYCHISCHE GESUNDHEIT ─────────────────────────────────────────────────
    "stress": {
        "category": "Psychische Gesundheit/Stress",
        "label": "Stress & Stressmanagement",
        "emoji": "🧠",
        "queries": [
            "chronic stress health effects cortisol",
            "workplace stress cardiovascular risk",
            "stress management intervention evidence-based",
            "mindfulness stress reduction MBSR clinical trial",
            "psychological stress immune function",
            "burnout prevention office workers",
        ],
        "keywords": ["stress", "cortisol", "burnout", "workplace stress", "mindfulness"],
        "boost_terms": ["randomized", "meta-analysis", "workplace", "office", "men"],
        "penalty_terms": ["PTSD combat", "war", "pediatric"],
    },
    "sucht": {
        "category": "Psychische Gesundheit/Sucht",
        "label": "Sucht & Abhängigkeit",
        "emoji": "⚠️",
        "queries": [
            "addiction prevention risk factors adults",
            "dopamine reward system addiction neuroscience",
            "digital addiction screen time mental health",
            "substance use disorder prevention",
            "gambling addiction prevalence",
        ],
        "keywords": ["addiction", "substance use", "dopamine", "reward", "dependence"],
        "boost_terms": ["prevention", "risk factors", "neuroscience", "intervention"],
        "penalty_terms": ["opioid treatment program", "detox clinic"],
    },
    # ── LIFESTYLE ─────────────────────────────────────────────────────────────
    "bildschirmzeit": {
        "category": "Lifestyle/Bildschirm",
        "label": "Bildschirmzeit & digitale Gesundheit",
        "emoji": "💻",
        "queries": [
            "screen time health effects adults",
            "blue light exposure sleep disruption",
            "digital eye strain prevention office workers",
            "social media mental health adults",
            "screen time sedentary behavior",
        ],
        "keywords": ["screen time", "blue light", "digital", "eye strain", "sedentary"],
        "boost_terms": ["adults", "office workers", "prevention", "intervention"],
        "penalty_terms": ["children", "pediatric", "adolescent screen time"],
    },
    "haltung_ruecken": {
        "category": "Lifestyle/Ergonomie",
        "label": "Haltung, Rücken & Ergonomie",
        "emoji": "🪑",
        "queries": [
            "low back pain office workers prevention",
            "ergonomics workstation design evidence",
            "sitting posture musculoskeletal pain",
            "standing desk health benefits",
            "core strengthening low back pain",
            "neck pain computer work prevention",
        ],
        "keywords": ["back pain", "posture", "ergonomics", "musculoskeletal", "spine", "sitting"],
        "boost_terms": ["office workers", "randomized", "prevention", "intervention"],
        "penalty_terms": ["surgical", "spinal surgery", "pediatric scoliosis"],
    },
    # ── RISIKEN ───────────────────────────────────────────────────────────────
    "risiko_alter_geschlecht": {
        "category": "Risiken/Demografie",
        "label": "Alter & Geschlechtsspezifische Risiken",
        "emoji": "📊",
        "queries": [
            "men health risks 30-40 preventive screening",
            "testosterone age decline health effects men",
            "cardiovascular risk men 35-45 prevention",
            "cancer screening men 35 colorectal prostate",
            "male health disparities prevention",
        ],
        "keywords": ["men health", "male", "testosterone", "cardiovascular risk", "screening"],
        "boost_terms": ["age 30-45", "men", "male", "prevention", "screening guidelines"],
        "penalty_terms": ["women", "female", "estrogen", "menopause"],
    },
    "risiko_sitzen": {
        "category": "Risiken/Beruf",
        "label": "Berufliche Risiken (Bürojob / Sitzen)",
        "emoji": "🏢",
        "queries": [
            "prolonged sitting mortality risk",
            "sedentary work cardiovascular disease",
            "occupational sitting breaks health",
            "desk job health consequences prevention",
            "physical inactivity office workers intervention",
        ],
        "keywords": ["sitting", "sedentary", "office", "occupational", "desk job"],
        "boost_terms": ["mortality risk", "cardiovascular", "intervention", "breaks"],
        "penalty_terms": ["manual labor", "construction workers"],
    },
    "risiko_familiengeschichte": {
        "category": "Risiken/Familie",
        "label": "Familiengeschichte & genetische Risiken",
        "emoji": "🧬",
        "queries": [
            "family history cardiovascular disease risk young men",
            "genetic risk factors prevention lifestyle",
            "familial hypercholesterolemia early intervention",
            "hereditary cancer risk prevention",
            "epigenetics lifestyle modification disease prevention",
        ],
        "keywords": ["family history", "genetic risk", "hereditary", "epigenetics", "prevention"],
        "boost_terms": ["men", "young adults", "intervention", "prevention", "lifestyle"],
        "penalty_terms": ["pediatric genetics", "rare disease"],
    },
}

# ─── API-Konfiguration ────────────────────────────────────────────────────────

NCBI_CONFIG = {
    "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    "api_key": None,          # Optional: https://www.ncbi.nlm.nih.gov/account/
    "email": "user@example.com",  # NCBI erfordert E-Mail-Angabe
    "rate_limit": 3,          # Requests/Sekunde (10 mit API-Key)
    "max_results_per_query": 50,
}

DOAJ_CONFIG = {
    "base_url": "https://doaj.org/api",
    "rate_limit": 2,
    "max_results_per_query": 50,
}

PLOS_CONFIG = {
    "base_url": "https://api.plos.org",
    "rate_limit": 2,
    "max_results_per_query": 50,
}

# ─── Relevanz-Scoring-Gewichte ────────────────────────────────────────────────

SCORING_CONFIG = {
    "weights": {
        "keyword_match": 0.30,       # Topic-Keywords im Titel/Abstract
        "boost_term_match": 0.25,    # Hochwertige Studientypen
        "study_type_bonus": 0.20,    # RCT > Cohort > Case study
        "recency_bonus": 0.15,       # Neuere Paper bevorzugt
        "open_access_bonus": 0.10,   # Volltext verfügbar
    },
    "study_type_scores": {
        "meta-analysis": 1.0,
        "systematic review": 0.9,
        "randomized controlled trial": 0.85,
        "cohort study": 0.7,
        "cross-sectional": 0.5,
        "case-control": 0.5,
        "review": 0.4,
        "case report": 0.2,
    },
    "recency_decay_years": 10,      # Volles Score für <10 Jahre
}
