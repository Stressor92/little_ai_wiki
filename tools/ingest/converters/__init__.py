"""
converters/__init__.py
Format-Registry und automatische Converter-Erkennung.
"""

from __future__ import annotations
from pathlib import Path
from typing import Type

from .base import BaseConverter, Document
from .pdf_conv import PDFConverter
from .epub_conv import EPUBConverter
from .docx_conv import DOCXConverter
from .other_conv import HTMLConverter, CalibreConverter, TXTConverter
from .tabular_conv import CSVConverter, XLSXConverter

# Alle verfügbaren Converter in Priorität-Reihenfolge
ALL_CONVERTERS: list[Type[BaseConverter]] = [
    PDFConverter,
    EPUBConverter,
    DOCXConverter,
    XLSXConverter,
    CSVConverter,
    HTMLConverter,
    CalibreConverter,
    TXTConverter,
]

# Extension → Converter-Mapping (automatisch aufgebaut)
_EXT_MAP: dict[str, Type[BaseConverter]] = {}
for _cls in ALL_CONVERTERS:
    for _ext in _cls.SUPPORTED_EXTENSIONS:
        _EXT_MAP[_ext.lower()] = _cls


def get_converter(path: Path) -> BaseConverter:
    """Gibt den passenden Converter für eine Datei zurück."""
    ext = path.suffix.lower()
    cls = _EXT_MAP.get(ext)
    if cls is None:
        supported = sorted(_EXT_MAP.keys())
        raise ValueError(
            f"Kein Converter für '{ext}' gefunden.\n"
            f"Unterstützte Formate: {', '.join(supported)}"
        )
    return cls()


def supported_extensions() -> list[str]:
    return sorted(_EXT_MAP.keys())


__all__ = [
    "get_converter",
    "supported_extensions",
    "ALL_CONVERTERS",
    "Document",
]
