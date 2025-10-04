# rag/__init__.py
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

from .config import load_config
from .runners.hirag import HiRAGRunner

def _ensure_utf8_stdio() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream and hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_ensure_utf8_stdio()



class RAG:
    """
    Tiny facade you can import anywhere:
        from rag import RAG
        rag = RAG("config.yaml")
        rag.build(["...text..."])        # or rag.build_from_file("books/x.txt")
        context = rag.retrieve("query")
        rag.answer("query")
    """
    def __init__(self, config_path: Optional[str] = None, **overrides):
        self.cfg = load_config(config_path, **overrides)

        self.graphs_root = Path(self.cfg.get("graphs_root", self.cfg["cache_dir"])).expanduser().resolve()
        self.graphs_root.mkdir(parents=True, exist_ok=True)

        self.graph_dir = Path(self.cfg.get("graph_dir", self.cfg.get("logdir", str(self.graphs_root)))).expanduser().resolve()
        self.graph_dir.mkdir(parents=True, exist_ok=True)

        cache_dir = Path(self.cfg["cache_dir"]).expanduser().resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.runner = HiRAGRunner(
            workdir=cache_dir,
            mode=self.cfg["mode"],
            run_id=self.cfg["run_id"],
            cache_dir=cache_dir,
            embedding_func=self.cfg.get("embedding_func"),
            enable_naive_rag=self.cfg.get("enable_naive_rag", True),
            chunk_prefix_len=self.cfg.get("chunk_prefix_len", 120),
            log_level=self.cfg.get("log_level", 20),
            node_hit_strategy=self.cfg.get("node_hit_strategy", "union"),
            **self.cfg.get("hirag_kwargs", {}),
        )

        self.logdir = Path(self.cfg.get("logdir", str(self.graph_dir))).expanduser().resolve()
        self.logdir.mkdir(parents=True, exist_ok=True)

    # ---- build -----------------------------------------------------------
    def build(self, docs: List[str]) -> None:
        self.runner.build_index(docs)

    def build_from_file(self, path: str) -> None:
        txt = Path(path).read_text(encoding="utf-8", errors="ignore")
        self.build([txt])

    # ---- retrieve / answer ----------------------------------------------
    def retrieve(self, query: str, top_k: int = 8) -> Dict[str, Any]:
        """Return the structured retrieval context for a query."""
        return self.runner.retrieve(query, top_k=top_k)

    def answer(self, query: str, top_k: int = 8, include_context: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """Generate an answer using the configured answer backend (OpenAI chat by default)."""
        if hasattr(self.runner, "answer"):
            return self.runner.answer(query, top_k=top_k, include_context=include_context, **kwargs)
        context = self.runner.retrieve(query, top_k=top_k)
        payload = {"answer": "", "context": context} if include_context else {"answer": ""}
        return payload

    # ---- dump index.json -------------------------------------------------
    def dump_index(self, out_path: str) -> None:
        self.runner.dump_index({}, Path(out_path), self.cfg["run_id"])

    # ---- health ----------------------------------------------------------
    def healthy(self) -> bool:
        return self.runner.health_check()

