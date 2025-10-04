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

    cache_root_setting = overrides.get("cache_root") or cfg.get("cache_root")
    if cache_root_setting:
        cache_root = _resolve_relative(cache_root_setting, cfg_dir)
    else:
        cache_root = (cfg_dir / "cache").resolve()

    cache_dir_setting = overrides.get("cache_dir")
    if cache_dir_setting:
        cache_dir = str(_resolve_relative(cache_dir_setting, cfg_dir))
    else:
        cache_dir = str(cache_root / "hi" / ".hi_cache")

    logdir_setting = overrides.get("logs_path") or cfg.get("logs_path")
    if logdir_setting:
        logdir = str(_resolve_relative(logdir_setting, cfg_dir))
    else:
        logdir = str(cache_root / "hi")

    run_id = overrides.get("run_id") or cfg.get("run_id") or "rag_run"
    mode = (cfg.get("modes", {}).get("hi", {}) or {}).get("mode", "hi")
    hi = cfg.get("modes", {}).get("hi", {})
    default_emb_cfg = cfg.get("default_embedding", {}) or {}

    embedding_func = overrides.get("embedding_func") or make_default_embedding(default_emb_cfg)

    out = {
        "run_id": run_id,
        "mode": mode,
        "cache_dir": cache_dir,
        "logdir": logdir,
        "embedding_func": embedding_func,
        "enable_naive_rag": bool(hi.get("enable_naive_rag", True)),
        "chunk_prefix_len": int(hi.get("chunk_prefix_len", 120)),
        "node_hit_strategy": str(hi.get("node_hit_strategy", "union")),
        "log_level": int(hi.get("log_level", 20)),
        "hirag_kwargs": {
            k: hi[k]
            for k in (
                "chunk_func","chunk_token_size","chunk_overlap_token_size",
                "tiktoken_model_name","graph_cluster_algorithm","max_graph_cluster_size",
                "graph_cluster_seed","node_embedding_algorithm","node2vec_params",
                "enable_hierachical_mode","special_community_report_llm_kwargs",
                "embedding_batch_num","embedding_func_max_async",
                "query_better_than_threshold","using_azure_openai",
                "enable_llm_cache"
            )
            if k in hi
        },
    }
    out.update({k: v for k, v in overrides.items() if v is not None})
    return out
