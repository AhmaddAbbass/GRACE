# rag/config.py
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .embeddings import make_default_embedding

_DOTENV_LOADED = False
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    _DOTENV_LOADED = True


def _resolve_relative(path_like: Union[str, Path], base: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (base / path).resolve()


def load_config(config_path: Optional[Union[str, Path]], **overrides) -> Dict[str, Any]:
    _load_dotenv_once()

    cfg: Dict[str, Any] = {}

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    cfg_dir = cfg_path.parent

    if cfg_path.exists():
        cfg.update(yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {})

    hi_cfg = (cfg.get("modes", {}).get("hi", {}) or {})
    mode = str(hi_cfg.get("mode", "hi"))

    run_id = overrides.get("run_id") or cfg.get("run_id") or "rag_run"

    logs_path_setting = overrides.get("logs_path")
    if logs_path_setting is None:
        logs_path_setting = cfg.get("logs_path")

    cache_dir_setting = overrides.get("cache_dir") or cfg.get("cache_dir")
    legacy_cache_root_setting = overrides.get("cache_root") or cfg.get("cache_root")

    logs_root: Optional[Path] = None
    if logs_path_setting:
        logs_root = _resolve_relative(logs_path_setting, cfg_dir)

    if cache_dir_setting:
        raw_cache_dir = _resolve_relative(cache_dir_setting, cfg_dir)
    elif legacy_cache_root_setting:
        raw_cache_dir = _resolve_relative(legacy_cache_root_setting, cfg_dir)
    elif logs_root is not None:
        raw_cache_dir = logs_root
    else:
        raw_cache_dir = (cfg_dir / "kgs").resolve()

    raw_cache_dir = Path(raw_cache_dir)

    if raw_cache_dir.name == ".hi_cache":
        cache_dir_path = raw_cache_dir
        graph_dir_path = raw_cache_dir.parent
        graph_root_path = graph_dir_path.parent
    elif len(raw_cache_dir.parts) >= 2 and raw_cache_dir.parts[-2:] == (mode, ".hi_cache"):
        cache_dir_path = raw_cache_dir
        graph_dir_path = raw_cache_dir.parent
        graph_root_path = graph_dir_path.parent
    elif raw_cache_dir.name == mode:
        graph_dir_path = raw_cache_dir
        cache_dir_path = graph_dir_path / ".hi_cache"
        graph_root_path = graph_dir_path.parent
    else:
        graph_root_path = raw_cache_dir
        graph_dir_path = graph_root_path / mode
        cache_dir_path = graph_dir_path / ".hi_cache"

    if logs_root is None:
        logs_root = graph_root_path
    else:
        logs_root = Path(logs_root)

    cache_dir_path = cache_dir_path.resolve()
    graph_dir_path = graph_dir_path.resolve()
    graphs_root_path = logs_root.resolve()

    default_emb_cfg = cfg.get("default_embedding", {}) or {}
    embedding_func = overrides.get("embedding_func") or make_default_embedding(default_emb_cfg)

    out = {
        "run_id": run_id,
        "mode": mode,
        "graphs_root": str(graphs_root_path),
        "graph_dir": str(graph_dir_path),
        "cache_root": str(graph_root_path.resolve()),
        "cache_dir": str(cache_dir_path),
        "logdir": str(graph_dir_path),
        "embedding_func": embedding_func,
        "enable_naive_rag": bool(hi_cfg.get("enable_naive_rag", True)),
        "chunk_prefix_len": int(hi_cfg.get("chunk_prefix_len", 120)),
        "node_hit_strategy": str(hi_cfg.get("node_hit_strategy", "union")),
        "log_level": int(hi_cfg.get("log_level", 20)),
        "hirag_kwargs": {
            k: hi_cfg[k]
            for k in (
                "chunk_func","chunk_token_size","chunk_overlap_token_size",
                "tiktoken_model_name","graph_cluster_algorithm","max_graph_cluster_size",
                "graph_cluster_seed","node_embedding_algorithm","node2vec_params",
                "enable_hierachical_mode","special_community_report_llm_kwargs",
                "embedding_batch_num","embedding_func_max_async",
                "query_better_than_threshold","using_azure_openai",
                "enable_llm_cache"
            )
            if k in hi_cfg
        },
    }

    for key, value in overrides.items():
        if value is not None:
            out[key] = value

    return out
