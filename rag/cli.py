"""Minimal command-line helpers for the rag package."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from rag import RAG

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = PACKAGE_ROOT / "config.yaml"
DEFAULT_BOOKS_DIR = PACKAGE_ROOT / "books"


def _resolve_book(path_str: str) -> Path:
    raw_path = Path(path_str)
    candidates: Iterable[Path] = (
        raw_path if raw_path.is_absolute() else Path.cwd() / raw_path,
        PACKAGE_ROOT / raw_path,
        DEFAULT_BOOKS_DIR / raw_path,
        DEFAULT_BOOKS_DIR / raw_path.name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Book file not found: {path_str}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build or dump HiRAG caches")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to config.yaml (defaults to rag/config.yaml)",
    )
    parser.add_argument(
        "--book",
        help="Path to a .txt file to ingest. Relative paths are resolved against the rag folder.",
    )
    parser.add_argument("--skip-dump", action="store_true", help="Skip writing index.json")
    parser.add_argument("--dump-only", action="store_true", help="Only dump index.json without inserting new docs")
    parser.add_argument("--cache", help="Override knowledge graph folder (.hi_cache parent or the .hi_cache itself)")
    parser.add_argument("--logdir", help="Override KGs root directory")
    args = parser.parse_args(argv)

    overrides = {}
    if args.cache:
        overrides["cache_dir"] = args.cache
    if args.logdir:
        overrides["logs_path"] = args.logdir

    rag = RAG(args.config, **overrides)

    if args.dump_only and args.book:
        parser.error("--dump-only may not be combined with --book")

    if args.book and not args.dump_only:
        book_path = _resolve_book(args.book)
        rag.build_from_file(str(book_path))

    if not args.skip_dump:
        out_dir = Path(rag.cfg.get("graph_dir", rag.cfg["logdir"]))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "index.json"
        rag.dump_index(str(out))

    print(f"[rag.cli] done run_id={rag.cfg['run_id']}")


if __name__ == "__main__":
    main()

