#!/usr/bin/env python3
"""
pdf_rename.py – Intelligentes Umbenennen von PDF-Dateien
=========================================================
Kürzt lange, unspezifische Dateinamen (typisch bei E-Book-Downloads)
auf das Wesentliche: Titel, Autor(en) und ggf. Jahr.

Quellen für Metadaten (Priorität):
  1. Eingebettete PDF-Metadaten  (pypdf)
  2. Filename-Parsing            (Regex-Heuristiken)

Verwendung:
  python pdf_rename.py /pfad/zum/ordner              # Vorschau (Dry-Run)
  python pdf_rename.py /pfad/zum/ordner --apply      # Umbenennen durchführen
  python pdf_rename.py /pfad/zum/ordner --apply --log renamed.csv
  python pdf_rename.py einzelne_datei.pdf --apply

Optionen:
  --apply          Umbenennung tatsächlich durchführen (ohne: nur Vorschau)
  --max-len N      Maximale Länge des neuen Dateinamens ohne .pdf (Standard: 80)
  --max-authors N  Maximale Anzahl angezeigter Autoren vor "et al." (Standard: 2)
  --log FILE       CSV-Logdatei mit Vorher/Nachher-Mapping (Standard: rename_log.csv)
  --no-meta        PDF-Metadaten ignorieren, nur Filename-Parsing verwenden
  --recursive      Unterordner rekursiv durchsuchen
  --quiet          Nur Fehler ausgeben
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# ── Abhängigkeit ──────────────────────────────────────────────────────────────
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# Konfiguration
# ══════════════════════════════════════════════════════════════════════════════

# Bekannte Quell-/Library-Muster, die aus dem Namen entfernt werden sollen
# (case-insensitive, tauchen meistens in Klammern am Ende auf)
NOISE_PATTERNS = [
    # z-library Varianten
    r"z[-\s]?lib(?:rary)?(?:\.\w+)*",
    r"1lib(?:\.\w+)*",
    r"zlibrary(?:\.\w+)*",
    # andere Piracy-Quellen
    r"b-ok(?:\.\w+)*",
    r"bookfi(?:\.\w+)*",
    r"libgen(?:\.\w+)*",
    r"library\s*genesis",
    r"sci[-\s]?hub(?:\.\w+)*",
    r"epub\.pub",
    r"pdfdrive(?:\.\w+)*",
    r"pdfroom(?:\.\w+)*",
    r"freepdfbook(?:\.\w+)*",
    r"booksc(?:\.\w+)*",
    r"anyflip(?:\.\w+)*",
    r"dokumen\.pub",
    # generische Domain-Muster am Ende (z. B. "example.org", "site.sk")
    r"[\w.-]+\.(?:sk|org|com|net|io|ru|cc|to)\b",
]

# Kompiliertes Gesamt-Regex für Noise (in Klammern)
_NOISE_RE = re.compile(
    r"\(\s*(?:" + "|".join(NOISE_PATTERNS) + r")(?:\s*,\s*(?:" + "|".join(NOISE_PATTERNS) + r"))*\s*\)",
    re.IGNORECASE,
)

# Zeichen, die im Dateinamen nicht erlaubt sind (Windows-kompatibel)
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Jahres-Pattern (1800–2099)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")

# Autoren-Block in Klammern: "(Vorname Nachname, Vorname Nachname, ...)"
# Erkennt: "Max Mustermann", "M. Mustermann", "Mustermann, Max" usw.
_AUTHOR_PAREN_RE = re.compile(
    r"\(([A-ZÄÖÜ][^()]{2,120}?(?:,\s*[A-ZÄÖÜ][^()]{2,80}?)*(?:\s+etc\.?)?)\)",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def read_pdf_metadata(path: Path) -> dict:
    """Liest eingebettete Metadaten aus einer PDF-Datei."""
    if not PYPDF_AVAILABLE:
        return {}
    try:
        reader = PdfReader(str(path), strict=False)
        meta = reader.metadata or {}
        return {
            "title":  (meta.title  or "").strip(),
            "author": (meta.author or "").strip(),
        }
    except Exception:
        return {}


def remove_noise(name: str) -> str:
    """Entfernt bekannte Quell-/Library-Klammerblöcke."""
    cleaned = _NOISE_RE.sub("", name)
    # Doppelte Leerzeichen und Leerzeichen vor Satzzeichen bereinigen
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def extract_year(text: str) -> str | None:
    """Extrahiert das erste plausible Jahr aus einem Text."""
    m = _YEAR_RE.search(text)
    return m.group(1) if m else None


def normalize_authors(raw: str, max_authors: int) -> str:
    """
    Normalisiert einen Autoren-String:
    - Trennt an Komma/Semikolon
    - Kürzt "etc." / "u.a." am Ende
    - Gibt "Nachname1, Nachname2 et al." zurück
    """
    # Trailing noise entfernen
    raw = re.sub(r"\s*(?:etc\.?|u\.a\.?|and others|et al\.?)$", "", raw, flags=re.I).strip()

    # Aufteilen
    parts = [p.strip() for p in re.split(r"[;,]", raw) if p.strip()]

    # Leere und sehr kurze Fragmente filtern (z. B. einzelne Buchstaben)
    parts = [p for p in parts if len(p) > 1]

    if not parts:
        return raw

    # Nachname extrahieren (letztes Wort oder "Nachname, Vorname"-Format)
    def lastname(s: str) -> str:
        s = s.strip()
        if "," in s:
            return s.split(",")[0].strip()
        tokens = s.split()
        return tokens[-1] if tokens else s

    surnames = [lastname(p) for p in parts]

    if len(surnames) > max_authors:
        return ", ".join(surnames[:max_authors]) + " et al."
    return ", ".join(surnames)


def sanitize_filename(name: str) -> str:
    """Entfernt/ersetzt Zeichen, die in Dateinamen nicht erlaubt sind."""
    name = _ILLEGAL_CHARS.sub("_", name)
    # Mehrfache Unterstriche und Leerzeichen normalisieren
    name = re.sub(r"_+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" _")
    return name


def truncate(text: str, max_len: int) -> str:
    """Kürzt auf max_len Zeichen ohne Wort mitten zu trennen."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len].rsplit(" ", 1)[0]
    return truncated.rstrip(" -_,")


# ══════════════════════════════════════════════════════════════════════════════
# Kern-Logik: Neuen Namen berechnen
# ══════════════════════════════════════════════════════════════════════════════

def build_new_name(
    original_stem: str,
    meta: dict,
    max_len: int,
    max_authors: int,
) -> str:
    """
    Berechnet den neuen Dateinamen (ohne .pdf) aus Metadaten + Filename-Parsing.

    Ausgabe-Format:
      Titel - Autor1, Autor2 (Jahr)
      Titel - Autor1 et al. (Jahr)
      Titel (Jahr)
      Titel - Autor1
      Titel
    """

    # ── 1. Titel ──────────────────────────────────────────────────────────────
    title = meta.get("title", "").strip()
    author = meta.get("author", "").strip()
    year: str | None = None

    # Noise aus Metadaten-Feldern entfernen (manche Einbetter schmuggeln das rein)
    title = remove_noise(title)
    author = remove_noise(author)

    # ── 2. Fallback: Filename-Parsing ─────────────────────────────────────────
    stem_clean = remove_noise(original_stem)
    year_from_stem = extract_year(stem_clean)

    if not title:
        # Jahr aus Stem entfernen für saubereren Titel
        title_candidate = re.sub(r"\(\s*\d{4}\s*\)", "", stem_clean).strip()
        # Autoren-Klammern entfernen
        author_match = _AUTHOR_PAREN_RE.search(title_candidate)
        if author_match:
            raw_authors_from_name = author_match.group(1)
            # Nur übernehmen wenn kein Autor aus Metadaten
            if not author:
                author = raw_authors_from_name
            title_candidate = (
                title_candidate[: author_match.start()]
                + title_candidate[author_match.end() :]
            ).strip()

        # Restliche leere Klammern entfernen
        title_candidate = re.sub(r"\(\s*\)", "", title_candidate).strip(" -_")
        title = title_candidate

    if not year:
        year = year_from_stem

    # ── 3. Autoren normalisieren ───────────────────────────────────────────────
    author_str = ""
    if author:
        author_str = normalize_authors(author, max_authors)

    # ── 4. Zusammensetzen ─────────────────────────────────────────────────────
    # Titel sicherstellen
    if not title:
        title = original_stem  # Notfall: Originalname behalten

    # Suffix zusammenbauen: " - Autor (Jahr)" / " - Autor" / " (Jahr)"
    suffix = ""
    if author_str and year:
        suffix = f" - {author_str} ({year})"
    elif author_str:
        suffix = f" - {author_str}"
    elif year:
        suffix = f" ({year})"

    # Titel kürzen, damit Suffix noch Platz hat
    available = max_len - len(suffix)
    if available < 10:
        available = 10  # Mindestlänge für den Titel
    short_title = truncate(title, available)

    result = sanitize_filename(short_title + suffix)

    # Finale Längenprüfung (edge case: sehr langer Autor-String)
    if len(result) > max_len:
        result = sanitize_filename(truncate(result, max_len))

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Dateien verarbeiten
# ══════════════════════════════════════════════════════════════════════════════

def collect_pdfs(path: Path, recursive: bool) -> list[Path]:
    """Sammelt alle .pdf-Dateien im angegebenen Pfad."""
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path.glob(pattern))


def unique_path(target: Path) -> Path:
    """Gibt einen eindeutigen Pfad zurück (fügt _2, _3 … an bei Konflikt)."""
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    counter = 2
    while True:
        candidate = target.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def process_files(
    pdfs: list[Path],
    apply: bool,
    max_len: int,
    max_authors: int,
    use_meta: bool,
    log_path: Path | None,
    quiet: bool,
) -> dict:
    """Verarbeitet alle PDFs und benennt sie ggf. um."""
    log_rows = []
    changed = skipped = errors = 0

    col_w = min(max(len(str(p.name)) for p in pdfs) + 2, 60) if pdfs else 40

    for pdf in pdfs:
        try:
            meta = read_pdf_metadata(pdf) if use_meta else {}
            new_stem = build_new_name(pdf.stem, meta, max_len, max_authors)
            new_name = new_stem + ".pdf"

            if new_name == pdf.name:
                if not quiet:
                    print(f"  {'─ GLEICH':10}  {pdf.name}")
                skipped += 1
                continue

            target = unique_path(pdf.parent / new_name)

            if not quiet:
                old_display = pdf.name if len(pdf.name) <= col_w else pdf.name[:col_w - 1] + "…"
                status = "✓ UMBENENNEN" if apply else "→ VORSCHAU  "
                print(f"  {status}  {old_display:<{col_w}}  →  {target.name}")

            log_rows.append({"original": str(pdf), "renamed": str(target)})
            changed += 1

            if apply:
                pdf.rename(target)

        except Exception as exc:
            errors += 1
            print(f"  ✗ FEHLER     {pdf.name}: {exc}", file=sys.stderr)

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    action = "umbenannt" if apply else "würden umbenannt werden"
    print(
        f"\n  Ergebnis: {changed} Datei(en) {action}, "
        f"{skipped} unverändert, {errors} Fehler."
    )
    if not apply and changed:
        print("  → Zum Ausführen --apply hinzufügen.\n")

    # ── Log schreiben ─────────────────────────────────────────────────────────
    if log_path and log_rows:
        mode = "a" if log_path.exists() else "w"
        with open(log_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["original", "renamed"])
            if mode == "w":
                writer.writeheader()
            writer.writerows(log_rows)
        print(f"  Log gespeichert: {log_path}")

    return {
        "changed": changed,
        "skipped": skipped,
        "errors": errors,
        "log_rows": len(log_rows),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="PDF-Dateien intelligent umbenennen (Titel · Autor · Jahr).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="PDF-Datei oder Ordner mit PDFs",
    )
    parser.add_argument("--domain", default="")
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Umbenennung tatsächlich durchführen (Standard: nur Vorschau)",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=80,
        metavar="N",
        help="Maximale Länge des neuen Namens ohne .pdf (Standard: 80)",
    )
    parser.add_argument(
        "--max-authors",
        type=int,
        default=2,
        metavar="N",
        help="Maximale Anzahl Autoren vor 'et al.' (Standard: 2)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("rename_log.csv"),
        metavar="FILE",
        help="CSV-Logdatei (Standard: rename_log.csv)",
    )
    parser.add_argument(
        "--no-meta",
        action="store_true",
        help="PDF-Metadaten ignorieren, nur Filename-Parsing",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Unterordner rekursiv durchsuchen",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Nur Fehler ausgeben",
    )

    args = parser.parse_args()

    selected_path = args.path or (Path(args.input) if args.input else None)
    if selected_path is None:
        print("  Fehler: Pfad fehlt. Nutze positional 'path' oder --input.", file=sys.stderr)
        return 1

    apply_mode = args.apply or args.force
    if args.dry_run:
        apply_mode = False

    # ── Voraussetzungen prüfen ─────────────────────────────────────────────────
    if not PYPDF_AVAILABLE and not args.no_meta:
        print(
            "  Hinweis: pypdf nicht installiert → nur Filename-Parsing aktiv.\n"
            "  Installation: pip install pypdf\n"
        )

    if not selected_path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {selected_path}", file=sys.stderr)
        return 1

    # ── Dateien sammeln ────────────────────────────────────────────────────────
    pdfs = collect_pdfs(selected_path, args.recursive)
    if not pdfs:
        print("  Keine PDF-Dateien gefunden.")
        return 0

    mode = "UMBENENNEN" if apply_mode else "VORSCHAU (kein --apply)"
    print(f"\n  pdf_rename.py  [{mode}]")
    print(f"  {len(pdfs)} PDF(s) gefunden in: {selected_path}\n")

    if args.output:
        print("  Hinweis: --output wird von diesem Tool nicht verwendet (Umbenennung erfolgt in-place).")

    summary = process_files(
        pdfs=pdfs,
        apply=apply_mode,
        max_len=args.max_len,
        max_authors=args.max_authors,
        use_meta=not args.no_meta,
        log_path=args.log if apply_mode else None,
        quiet=args.quiet,
    )

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool": "rename_pdf",
            "domain": args.domain,
            "input": str(selected_path),
            "dry_run": not apply_mode,
            "recursive": args.recursive,
            "summary": summary,
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())