"""Configuration loader for the GRACE backend server."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import yaml

from rag.config import load_config as load_rag_config


@dataclass(frozen=True)
class SummarySettings:
    prompt: str
    model: str
    max_chunks: int
    max_chars_per_chunk: int


@dataclass(frozen=True)
class AppSettings:
    cors_origins: List[str]
    auth_required: bool


@dataclass(frozen=True)
class ServerSettings:
    rag_config_path: Path
    graphs_root: Path
    default_top_k: int
    default_top_m: int
    summary: SummarySettings
    app: AppSettings


def _resolve_path(value: Any, *, base: Path) -> Path:
    path = Path(str(value)) if value is not None else base
    return (path if path.is_absolute() else (base / path)).expanduser().resolve()


@lru_cache(maxsize=1)
def load_server_settings(config_path: Optional[str] = None) -> ServerSettings:
    base_dir = Path(__file__).resolve().parent
    cfg_path = Path(config_path) if config_path else base_dir / "config.yaml"

    raw_cfg: dict[str, Any] = {}
    if cfg_path.exists():
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Server config must be a mapping")
        raw_cfg = loaded

    rag_config_path = _resolve_path(raw_cfg.get("rag_config_path", "../rag/config.yaml"), base=base_dir)
    rag_cfg = load_rag_config(str(rag_config_path))

    graphs_root = _resolve_path(
        raw_cfg.get("graphs_root") or rag_cfg.get("graphs_root") or "../rag/kgs",
        base=base_dir,
    )

    default_top_k = int(raw_cfg.get("default_top_k", 8))
    default_top_m = int(raw_cfg.get("default_top_m", 2))

    summary_cfg = raw_cfg.get("summary") or {}
    if not isinstance(summary_cfg, dict):
        raise ValueError("summary section must be a mapping if provided")
    summary_settings = SummarySettings(
        prompt=summary_cfg.get("prompt") or (
            "You are a helpful assistant that writes short overviews of knowledge graphs. "
            "Mention the domain focus, key entity types, and example questions the graph can answer."
        ),
        model=summary_cfg.get("model") or "gpt-4o-mini",
        max_chunks=int(summary_cfg.get("max_chunks", 4)),
        max_chars_per_chunk=int(summary_cfg.get("max_chars_per_chunk", 600)),
    )

    app_cfg = raw_cfg.get("app") or {}
    if not isinstance(app_cfg, dict):
        raise ValueError("app section must be a mapping if provided")
    cors_origins = app_cfg.get("cors_origins") or ["*"]
    if isinstance(cors_origins, str):
        cors_origins = [cors_origins]
    app_settings = AppSettings(
        cors_origins=[str(origin) for origin in cors_origins],
        auth_required=bool(app_cfg.get("auth_required", False)),
    )

    return ServerSettings(
        rag_config_path=rag_config_path,
        graphs_root=graphs_root,
        default_top_k=default_top_k,
        default_top_m=default_top_m,
        summary=summary_settings,
        app=app_settings,
    )


SETTINGS = load_server_settings()


__all__ = ["SummarySettings", "AppSettings", "ServerSettings", "SETTINGS", "load_server_settings"]
