"""Utility helpers for the GRACE Flask server."""
from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

ROOT = Path(__file__).resolve().parent
_GRACE_ROOT = ROOT.parent
if str(_GRACE_ROOT) not in sys.path:
    sys.path.append(str(_GRACE_ROOT))

from rag import RAG  # type: ignore


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> Dict[str, Any]:
    cfg_path = Path(path or (ROOT / "config.yaml"))
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Config must be a mapping")
    return data


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    cfg = load_config()
    level_name = (cfg.get("logging", {}) or {}).get("level", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger = logging.getLogger("grace.server")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


@lru_cache(maxsize=1)
def make_rag() -> RAG:
    cfg = load_config()
    rag_cfg = cfg.get("rag", {}) or {}
    rag_config_path = rag_cfg.get("config_path")
    return RAG(rag_config_path)


def summarise_text_units(units: Iterable[Dict[str, Any]]) -> List[str]:
    snippets: List[str] = []
    for idx, unit in enumerate(units or [], start=1):
        content = (unit or {}).get("content", "")
        if content:
            snippets.append(f"[Graph-{idx}] {content.strip()}")
    return snippets


def build_health_payload() -> Dict[str, Any]:
    rag = make_rag()
    healthy = False
    try:
        healthy = bool(rag.healthy())
    except Exception:
        healthy = False
    return {"rag": healthy}


__all__ = ["load_config", "make_rag", "get_logger", "summarise_text_units", "build_health_payload"]
