"""Utility helpers for GRACE server endpoints."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rag import RAG

from .config import SETTINGS, ServerSettings


@dataclass(frozen=True)
class KGInfo:
    kg_id: str
    name: str
    mode: str
    graph_dir: Path
    cache_dir: Path
    history_dir: Path
    index_path: Path
    summary_path: Path


def _compose_display_name(name: str, mode: str) -> str:
    pretty = name.replace("_", " ").title()
    return f"{pretty} KG ({mode} mode)"


def _compose_kg_id(name: str, mode: str) -> str:
    return f"{name}/{mode}"


def _discover_kgs(settings: ServerSettings) -> Dict[str, KGInfo]:
    registry: Dict[str, KGInfo] = {}
    root = settings.graphs_root
    if not root.exists():
        return registry

    for graph_dir in root.glob("*/*"):
        if not graph_dir.is_dir():
            continue
        cache_dir = graph_dir / ".hi_cache"
        if not cache_dir.is_dir():
            continue
        name = graph_dir.parent.name
        mode = graph_dir.name
        kg_id = _compose_kg_id(name, mode)
        history_dir = graph_dir / "history"
        index_path = graph_dir / "index.json"
        summary_path = graph_dir / "summary.txt"
        registry[kg_id] = KGInfo(
            kg_id=kg_id,
            name=name,
            mode=mode,
            graph_dir=graph_dir,
            cache_dir=cache_dir,
            history_dir=history_dir,
            index_path=index_path,
            summary_path=summary_path,
        )
    return dict(sorted(registry.items(), key=lambda item: item[0]))


@lru_cache(maxsize=1)
def get_registry() -> Dict[str, KGInfo]:
    return _discover_kgs(SETTINGS)


def refresh_registry() -> None:
    get_registry.cache_clear()
    get_registry()
    get_rag_for_kg.cache_clear()


def list_kgs() -> List[KGInfo]:
    return list(get_registry().values())


def get_kg_info(kg_id: str) -> KGInfo:
    registry = get_registry()
    if kg_id not in registry:
        raise KeyError(kg_id)
    return registry[kg_id]


def _directory_size(path: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for name in filenames:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except FileNotFoundError:
                continue
    return total


def _load_index(info: KGInfo) -> Optional[Dict[str, Any]]:
    if not info.index_path.exists():
        return None
    try:
        return json.loads(info.index_path.read_text(encoding="utf-8"))
    except Exception:
        return None

def load_chunk_samples(info: KGInfo, max_chunks: int, max_chars: int) -> List[str]:
    chunks_path = info.cache_dir / "kv_store_text_chunks.json"
    if not chunks_path.exists():
        return []
    try:
        data = json.loads(chunks_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    samples: List[str] = []
    for entry in data.values():
        content = (entry or {}).get("content") if isinstance(entry, dict) else None
        if not content:
            continue
        snippet = str(content)[:max_chars].strip()
        if snippet:
            samples.append(snippet)
        if len(samples) >= max_chunks:
            break
    return samples


def build_kg_metadata(info: KGInfo) -> Dict[str, Any]:
    index_payload = _load_index(info) or {}
    nodes = index_payload.get("nodes") or []
    edges = index_payload.get("edges") or []

    try:
        updated_ts = datetime.fromtimestamp(info.index_path.stat().st_mtime, tz=datetime.now().astimezone().tzinfo)
        updated_at = updated_ts.isoformat()
    except FileNotFoundError:
        updated_at = None

    summary_status = "ready" if info.summary_path.exists() and info.summary_path.stat().st_size > 0 else "building"

    return {
        "kg_id": info.kg_id,
        "name": _compose_display_name(info.name, info.mode),
        "path": str(info.graph_dir),
        "size_bytes": _directory_size(info.graph_dir),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "updated_at": updated_at,
        "summary_status": summary_status,
    }


@lru_cache(maxsize=32)
def get_rag_for_kg(kg_id: str) -> RAG:
    info = get_kg_info(kg_id)
    overrides = {
        "graph_dir": str(info.graph_dir),
        "cache_dir": str(info.cache_dir),
        "graphs_root": str(SETTINGS.graphs_root),
        "logdir": str(info.graph_dir),
    }
    return RAG(str(SETTINGS.rag_config_path), **overrides)


def load_index_payload(info: KGInfo) -> Dict[str, Any]:
    payload = _load_index(info)
    if payload is None:
        raise FileNotFoundError(f"index.json not found for {info.kg_id}")
    return payload


def generate_run_id(existing: Optional[str] = None) -> str:
    return existing or f"run_{uuid.uuid4().hex[:12]}"


def generate_qid() -> str:
    return f"q_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def _parse_ts(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def collect_history_items(run_id: str, limit: int, before_qid: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    entries: List[Tuple[float, Dict[str, Any]]] = []
    threshold_ts: Optional[float] = None

    if before_qid:
        for info in list_kgs():
            run_dir = info.history_dir / run_id
            ctx_path = run_dir / before_qid / "context.json"
            if ctx_path.exists():
                try:
                    data = json.loads(ctx_path.read_text(encoding="utf-8"))
                    threshold_ts = _parse_ts(str(data.get("ts", "")))
                    break
                except Exception:
                    continue

    for info in list_kgs():
        run_dir = info.history_dir / run_id
        if not run_dir.exists():
            continue
        for qdir in run_dir.iterdir():
            context_path = qdir / "context.json"
            if not context_path.exists():
                continue
            try:
                data = json.loads(context_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("run_id") != run_id:
                continue
            ts_value = _parse_ts(str(data.get("ts", "")))
            if threshold_ts is not None and ts_value >= threshold_ts:
                continue
            entries.append((ts_value, {"kg_id": info.kg_id, "payload": data}))

    entries.sort(key=lambda item: item[0], reverse=True)
    sliced = entries[:limit]
    next_qid = None
    if len(entries) > limit:
        next_payload = entries[limit][1]
        next_qid = next_payload["payload"]["qid"]

    return [entry for _, entry in sliced], next_qid


__all__ = [
    "KGInfo",
    "build_kg_metadata",
    "collect_history_items",
    "generate_qid",
    "generate_run_id",
    "get_kg_info",
    "get_rag_for_kg",
    "list_kgs",
    "load_chunk_samples",
    "load_index_payload",
    "refresh_registry",
]
