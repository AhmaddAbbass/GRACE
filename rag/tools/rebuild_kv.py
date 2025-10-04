"""Rebuild missing HiRAG KV stores (full docs, text chunks, community reports) without rerunning ingestion."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from rag import RAG

from hirag._op import generate_community_report, get_chunks
from hirag._utils import compute_mdhash_id

DEFAULT_SEPARATOR = "<sep>"


def _load_documents(source_path: Path, separator: str) -> Dict[str, Dict[str, str]]:
    text = source_path.read_text(encoding="utf-8", errors="ignore")
    parts = [segment.strip() for segment in text.split(separator) if segment.strip()]
    if not parts:
        raise ValueError(f"No documents found in {source_path} using separator {separator!r}")
    return {compute_mdhash_id(part, prefix="doc-"): {"content": part} for part in parts}


async def _flush_kv_stores(core) -> None:
    await core.full_docs.index_done_callback()
    await core.text_chunks.index_done_callback()
    await core.community_reports.index_done_callback()


async def _rebuild(args: argparse.Namespace) -> None:
    kg_dir: Path = args.kg_dir.resolve()
    cache_dir = kg_dir / ".hi_cache"
    if not cache_dir.is_dir():
        raise FileNotFoundError(f"Expected HiRAG cache at {cache_dir}")

    source_path: Path = args.source.resolve()
    documents = _load_documents(source_path, args.separator)
    print(f"Loaded {len(documents)} documents from {source_path}")

    overrides = {
        "graph_dir": str(kg_dir),
        "cache_dir": str(cache_dir),
        "graphs_root": str(kg_dir.parent),
        "run_id": args.run_id or "rebuild_kv",
    }
    rag = RAG(args.config, **overrides)
    core = rag.runner._rag  # access underlying HiRAG instance

    if args.drop_existing:
        print("Dropping existing KV stores before rebuild ...")
        await core.full_docs.drop()
        await core.text_chunks.drop()
        await core.community_reports.drop()

    print("Upserting full documents ...")
    await core.full_docs.upsert(documents)

    print("Creating text chunks ...")
    chunks = get_chunks(
        new_docs=documents,
        chunk_func=core.chunk_func,
        overlap_token_size=core.chunk_overlap_token_size,
        max_token_size=core.chunk_token_size,
    )
    await core.text_chunks.upsert(chunks)
    print(f"Inserted {len(chunks)} text chunks")

    print("Rebuilding community reports ...")
    await core.community_reports.drop()
    await core.chunk_entity_relation_graph.clustering(core.graph_cluster_algorithm)
    await generate_community_report(
        core.community_reports,
        core.chunk_entity_relation_graph,
        asdict(core),
    )

    await _flush_kv_stores(core)
    print("Community reports regenerated successfully")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg-dir", required=True, type=Path, help="Path to the HiRAG graph directory (e.g. rag/kgs/cooking_kg/hi)")
    parser.add_argument("--source", required=True, type=Path, help="Original text file that was ingested")
    parser.add_argument("--config", default="rag/config.yaml", type=str, help="Path to rag config (defaults to rag/config.yaml)")
    parser.add_argument("--separator", default=DEFAULT_SEPARATOR, help="Separator used between documents in the source text")
    parser.add_argument("--run-id", default=None, help="Run ID used when instantiating RAG")
    parser.add_argument("--drop-existing", action="store_true", help="Drop existing KV entries before rebuilding")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_rebuild(args))


if __name__ == "__main__":
    main()
