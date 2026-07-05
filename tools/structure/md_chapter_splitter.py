#!/usr/bin/env python3
"""
split_chapters.py
=================
Zerlegt konvertierte Markdown-Dateien in einzelne Kapitel-Dateien.

Jede Quelldatei  →  mehrere Ausgabedateien:
  buch.md  →  buch_001_Einleitung.md
               buch_002_Kapitel_1.md
               buch_003_Methoden.md
               ...

Verwendet die Markdown-Überschriften-Hierarchie als Kapitel-Grenzen.
Wählt automatisch den besten Split-Level (H1 → H2 → H3).

Verwendung:
  # Einzelne Datei
  python split_chapters.py buch.md

  # Ordner → Zielordner
  python split_chapters.py ./converted/ ./chapters/

  # Mit Optionen
  python split_chapters.py ./input/ ./output/ --level 2 --min-words 50
  python split_chapters.py ./input/ ./output/ --recursive --dry-run
  python split_chapters.py buch.md --no-frontmatter --no-toc
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─── Datenstrukturen ──────────────────────────────────────────────────────────

@dataclass
class Chapter:
    number:    int
    level:     int              # Heading-Level (1–4)
    title:     str
    lines:     list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(l.split()) for l in self.lines)

    @property
    def safe_title(self) -> str:
        """Dateiname-sicherer Titel (max 60 Zeichen)."""
        t = re.sub(r'[^\w\s-]', '', self.title)
        t = re.sub(r'\s+', '_', t.strip())
        t = re.sub(r'_+', '_', t)
        return t[:60].strip('_') or f"Kapitel_{self.number}"


@dataclass
class ParsedDocument:
    frontmatter:     dict[str, str]
    frontmatter_raw: str            # Original YAML-Block (für Ausgabe)
    preamble:        list[str]      # Zeilen vor erstem Kapitel
    chapters:        list[Chapter]
    source_path:     Path
    split_level:     int


# ─── Frontmatter-Parsing ──────────────────────────────────────────────────────

def parse_frontmatter(lines: list[str]) -> tuple[dict, str, int]:
    """
    Parst YAML-Frontmatter (--- … ---).
    Gibt (dict, raw_yaml_string, lines_consumed) zurück.
    Kein externer YAML-Parser nötig — nur einfaches Key-Value-Parsing.
    """
    if not lines or lines[0].strip() != "---":
        return {}, "", 0

    end = next(
        (i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"),
        None,
    )
    if end is None:
        return {}, "", 0

    yaml_lines = lines[1:end]
    raw        = "---\n" + "\n".join(yaml_lines) + "\n---"
    meta: dict[str, str] = {}

    for line in yaml_lines:
        m = re.match(r'^(\w[\w_-]*):\s*(.*)$', line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"\'')
            meta[key] = val

    return meta, raw, end + 1


# ─── Dokument-Parsing ─────────────────────────────────────────────────────────

HEADING_RE = re.compile(r'^(#{1,4})\s+(.+)')


def detect_split_level(lines: list[str], override: Optional[int]) -> int:
    """
    Wählt den optimalen Split-Level:
      - Override durch --level?  → direkt verwenden
      - H1 vorhanden?            → Split auf H1
      - Sonst H2, H3, H4
    """
    if override:
        return override

    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            counts[lvl] += 1

    # Bevorzuge den obersten Level mit mehr als 1 Überschrift
    for lvl in [1, 2, 3, 4]:
        if counts[lvl] > 1:
            log.debug(f"  Auto Split-Level: H{lvl} ({counts[lvl]}x gefunden)")
            return lvl

    # Genau eine Überschrift → trotzdem diesen Level verwenden
    for lvl in [1, 2, 3, 4]:
        if counts[lvl] == 1:
            return lvl

    return 1  # Fallback


def parse_document(path: Path, level_override: Optional[int]) -> ParsedDocument:
    """Liest .md-Datei und zerlegt sie in Frontmatter + Kapitel."""
    text  = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Frontmatter extrahieren
    meta, raw_fm, fm_end = parse_frontmatter(lines)
    body = lines[fm_end:]

    # Split-Level bestimmen
    split_level = detect_split_level(body, level_override)

    preamble: list[str] = []
    chapters: list[Chapter] = []
    current: Optional[Chapter] = None

    for line in body:
        m = HEADING_RE.match(line)
        if m:
            lvl = len(m.group(1))
            title = m.group(2).strip()

            if lvl == split_level:
                # Neues Kapitel
                if current:
                    chapters.append(current)
                current = Chapter(
                    number=len(chapters) + 1,
                    level=lvl,
                    title=title,
                )
                continue  # Heading-Zeile nicht in .lines aufnehmen

            elif lvl < split_level:
                # Überschrift über dem Split-Level → in Preamble
                if current:
                    chapters.append(current)
                    current = None
                preamble.append(line)
                continue

        # Normale Zeile
        if current is not None:
            current.lines.append(line)
        else:
            preamble.append(line)

    if current:
        chapters.append(current)

    # Kapitel neu nummerieren (nach Filterung)
    for i, ch in enumerate(chapters, 1):
        ch.number = i

    return ParsedDocument(
        frontmatter=meta,
        frontmatter_raw=raw_fm,
        preamble=preamble,
        chapters=chapters,
        source_path=path,
        split_level=split_level,
    )


# ─── Ausgabe-Generierung ──────────────────────────────────────────────────────

def make_chapter_frontmatter(
    parent: ParsedDocument,
    chapter: Chapter,
    total_chapters: int,
) -> str:
    """Erstellt YAML-Frontmatter für ein Kapitel-File."""
    m = parent.frontmatter
    title       = chapter.title
    parent_title= m.get("title", parent.source_path.stem)
    author      = m.get("author", "")
    source_fmt  = m.get("source_format", "")
    source_file = m.get("source_file", parent.source_path.name)

    lines = [
        "---",
        f'title: "{_esc(title)}"',
        f'parent_title: "{_esc(parent_title)}"',
        f'chapter: {chapter.number}',
        f'chapters_total: {total_chapters}',
        f'split_level: {chapter.level}',
    ]
    if author:
        lines.append(f'author: "{_esc(author)}"')
    if source_fmt:
        lines.append(f'source_format: "{source_fmt}"')
    lines.append(f'source_file: "{source_file}"')

    # Restliche Felder aus Eltern-Frontmatter übernehmen
    skip = {"title", "author", "source_format", "source_file", "chapters",
            "converted", "pages", "description"}
    for k, v in m.items():
        if k not in skip:
            lines.append(f'{k}: "{_esc(v)}"')

    lines.append(f'split_date: "{datetime.now().strftime("%Y-%m-%d")}"')
    lines.append("---")
    return "\n".join(lines)


def make_chapter_content(chapter: Chapter) -> str:
    """Erstellt den Markdown-Inhalt eines Kapitels."""
    heading = "#" * chapter.level + f" {chapter.title}"
    body    = "\n".join(chapter.lines).strip()

    # Trailing-Whitespace-Zeilen bereinigen
    body = re.sub(r'\n{3,}', '\n\n', body)

    if body:
        return f"{heading}\n\n{body}\n"
    return f"{heading}\n"


def make_toc(doc: ParsedDocument, chapter_files: list[Path]) -> str:
    """Erstellt eine _toc.md Inhaltsverzeichnis-Datei."""
    m           = doc.frontmatter
    title       = m.get("title", doc.source_path.stem)
    author      = m.get("author", "")
    source_fmt  = m.get("source_format", "")

    lines = [
        "---",
        f'title: "Inhaltsverzeichnis — {_esc(title)}"',
        f'type: toc',
        f'source_file: "{doc.source_path.name}"',
        f'chapters_total: {len(doc.chapters)}',
        f'generated: "{datetime.now().strftime("%Y-%m-%d %H:%M")}"',
        "---",
        "",
        f"# {title}",
        "",
    ]
    if author:
        lines.append(f"**Autor:** {author}  ")
    if source_fmt:
        lines.append(f"**Format:** {source_fmt}  ")
    lines += [
        f"**Kapitel:** {len(doc.chapters)}",
        "",
        "---",
        "",
        "## Inhaltsverzeichnis",
        "",
    ]

    for ch, filepath in zip(doc.chapters, chapter_files):
        rel = filepath.name
        wc  = ch.word_count
        lines.append(f"{ch.number:>3}. [{ch.title}]({rel})  _{wc:,} Wörter_")

    lines += ["", "---", ""]
    if doc.preamble:
        preamble_text = "\n".join(doc.preamble).strip()
        if preamble_text:
            lines += [
                "## Einleitung / Vorbemerkung",
                "",
                preamble_text,
                "",
            ]

    return "\n".join(lines)


# ─── Dateinamen ───────────────────────────────────────────────────────────────

def chapter_filename(stem: str, chapter: Chapter, total: int) -> str:
    """Erzeugt den Dateinamen: stem_NNN_Titel.md"""
    # Breite der Nummer an Gesamt-Anzahl anpassen (min 3 Stellen)
    width = max(3, len(str(total)))
    num   = str(chapter.number).zfill(width)
    safe  = chapter.safe_title
    if safe:
        return f"{stem}_{num}_{safe}.md"
    return f"{stem}_{num}.md"


def toc_filename(stem: str) -> str:
    return f"{stem}_000_TOC.md"


# ─── Splitting ────────────────────────────────────────────────────────────────

def split_file(
    input_path: Path,
    output_dir: Path,
    level_override: Optional[int],
    min_words: int,
    add_frontmatter: bool,
    add_toc: bool,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Splittet eine .md-Datei in Kapitel.
    Gibt (erzeugte Dateien, übersprungene Kapitel) zurück.
    """
    log.info(f"📖 {input_path.name}")

    doc = parse_document(input_path, level_override)

    if not doc.chapters:
        log.warning(f"   ⚠  Keine Kapitel (H{doc.split_level}) gefunden — übersprungen")
        return 0, 0

    stem   = input_path.stem
    n_skip = 0
    chapter_files: list[Path] = []

    # Kapitel filtern und Pfade bestimmen
    valid_chapters = []
    for ch in doc.chapters:
        if ch.word_count < min_words:
            log.debug(f"   ⏭  #{ch.number} '{ch.title}' — nur {ch.word_count} Wörter (< {min_words})")
            n_skip += 1
            continue
        fname  = chapter_filename(stem, ch, len(doc.chapters))
        fpath  = output_dir / fname
        valid_chapters.append((ch, fpath))
        chapter_files.append(fpath)

    if not valid_chapters:
        log.warning(f"   ⚠  Alle Kapitel unter Mindestwortanzahl ({min_words}) — übersprungen")
        return 0, n_skip

    log.info(
        f"   Split-Level: H{doc.split_level} | "
        f"{len(valid_chapters)} Kapitel | "
        f"{n_skip} übersprungen"
    )

    if dry_run:
        for ch, fp in valid_chapters:
            log.info(f"   [DRY] → {fp.name}  ({ch.word_count:,} Wörter)")
        return 0, n_skip

    output_dir.mkdir(parents=True, exist_ok=True)
    n_written = 0

    # Kapitel-Dateien schreiben
    for ch, fpath in valid_chapters:
        if fpath.exists() and not overwrite:
            log.info(f"   ⏭  {fpath.name} (existiert)")
            continue

        parts = []
        if add_frontmatter:
            parts.append(make_chapter_frontmatter(doc, ch, len(doc.chapters)))
        parts.append(make_chapter_content(ch))
        content = "\n\n".join(parts)

        fpath.write_text(content, encoding="utf-8")
        log.info(f"   ✓  {fpath.name}  ({ch.word_count:,} Wörter)")
        n_written += 1

    # TOC schreiben
    if add_toc and chapter_files:
        toc_path = output_dir / toc_filename(stem)
        if not toc_path.exists() or overwrite:
            toc_path.write_text(make_toc(doc, chapter_files), encoding="utf-8")
            log.info(f"   📋 {toc_path.name}")

    return n_written, n_skip


# ─── Batch-Verarbeitung ───────────────────────────────────────────────────────

def collect_md_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".md" else []
    pattern = "**/*.md" if recursive else "*.md"
    # TOC- und bereits gesplittete Dateien überspringen
    return sorted(
        f for f in path.glob(pattern)
        if not f.stem.endswith("_TOC")
        and not re.search(r'_\d{3,}(_|$)', f.stem)
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Markdown → einzelne Kapitel-Dateien",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Beispiele:
              python split_chapters.py buch.md
              python split_chapters.py ./input/ ./output/
              python split_chapters.py ./input/ ./output/ --level 2
              python split_chapters.py ./input/ ./output/ --recursive --dry-run
              python split_chapters.py buch.md --min-words 200 --no-toc
        """),
    )

    p.add_argument(
        "source",
        nargs="?",
        help="Quelldatei (.md) oder Quellordner",
    )
    p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Zielordner (default: Unterordner 'chapters/' neben der Quelle)",
    )
    p.add_argument(
        "--level", "-l",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Überschriften-Level für Kapitel-Splits (default: auto)",
    )
    p.add_argument(
        "--min-words", "-m",
        type=int,
        default=30,
        metavar="N",
        help="Kapitel mit weniger als N Wörtern überspringen (default: 30)",
    )
    p.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Unterordner einschließen",
    )
    p.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Kein YAML-Frontmatter in Kapitel-Dateien",
    )
    p.add_argument(
        "--no-toc",
        action="store_true",
        help="Keine Inhaltsverzeichnis-Datei (_000_TOC.md) erzeugen",
    )
    p.add_argument(
        "--flat",
        action="store_true",
        help="Alle Kapitel in denselben Zielordner (kein Unterordner pro Buch)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Vorhandene Dateien überschreiben",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Vorschau: zeige was erzeugt würde, ohne zu schreiben",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Bei Fehler nächste Datei verarbeiten",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Debug-Ausgabe",
    )
    p.add_argument("--domain", default="")
    p.add_argument("--input", default="")
    p.add_argument("--output", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--report", default="")
    p.add_argument("--config", default="")
    p.add_argument("--workers", type=int, default=1)

    return p.parse_args()


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """YAML-String escapen."""
    return s.replace('"', '\\"').replace('\n', ' ')


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds//60)}m {seconds%60:.0f}s"


# ─── Hauptprogramm ────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    source_arg = args.source or args.input
    if not source_arg:
        log.error("Quelle fehlt. Nutze positional 'source' oder --input.")
        return 1

    source = Path(source_arg).resolve()
    if not source.exists():
        log.error(f"Quelle nicht gefunden: {source}")
        return 1

    # Dateien sammeln
    files = collect_md_files(source, args.recursive)
    if not files:
        log.error(f"Keine .md-Dateien in: {source}")
        return 1

    # Zielordner bestimmen
    base_target = (
        Path(args.output).resolve()
        if args.output
        else Path(args.target).resolve()
        if args.target
        else (source.parent / "chapters" if source.is_file() else source / "chapters")
    )

    import time
    t0 = time.monotonic()

    log.info(f"\n{'═'*58}")
    log.info(f"  📂 Kapitel-Splitter")
    log.info(f"  Dateien:  {len(files)}")
    log.info(f"  Ziel:     {base_target}")
    if args.dry_run:
        log.info(f"  Modus:    DRY-RUN (keine Dateien werden geschrieben)")
    log.info(f"{'═'*58}\n")

    total_written = total_skipped = total_errors = 0

    for i, md_file in enumerate(files, 1):
        log.info(f"[{i}/{len(files)}]")

        # Zielordner: bei Batch je Buch eigener Unterordner (außer --flat)
        if source.is_dir() and not args.flat:
            rel = md_file.relative_to(source)
            output_dir = base_target / rel.parent / rel.stem
        else:
            output_dir = base_target

        try:
            written, skipped = split_file(
                input_path     = md_file,
                output_dir     = output_dir,
                level_override = args.level,
                min_words      = args.min_words,
                add_frontmatter= not args.no_frontmatter,
                add_toc        = not args.no_toc,
                overwrite      = args.overwrite or args.force,
                dry_run        = args.dry_run,
            )
            total_written  += written
            total_skipped  += skipped

        except Exception as e:
            log.error(f"   ✗ Fehler: {e}")
            if args.verbose:
                import traceback; traceback.print_exc()
            total_errors += 1
            if not args.continue_on_error:
                log.error("Abbruch. Nutze --continue-on-error für Batch-Modus.")
                return 1

        log.info("")

    elapsed = time.monotonic() - t0
    log.info(f"{'─'*58}")
    log.info(
        f"  ✓ {total_written} Kapitel-Dateien erzeugt  |  "
        f"⏭ {total_skipped} übersprungen  |  "
        f"✗ {total_errors} Fehler  |  "
        f"{_fmt_duration(elapsed)}"
    )
    if not args.dry_run:
        log.info(f"  Ausgabe: {base_target}")
    log.info(f"{'─'*58}\n")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool": "md_chapter_splitter",
            "domain": args.domain,
            "input": str(source),
            "output": str(base_target),
            "dry_run": args.dry_run,
            "files": len(files),
            "written": total_written,
            "skipped": total_skipped,
            "errors": total_errors,
            "elapsed_seconds": round(elapsed, 6),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())