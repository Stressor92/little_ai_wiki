"""Compatibility shim. Canonical evidence index stage is tools.indexing.index_creator."""

from tools.indexing.index_creator import build_index, main

__all__ = ["build_index", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
