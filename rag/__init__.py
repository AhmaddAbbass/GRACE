# rag/__init__.py
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import load_config
from .runners.hirag import HiRAGRunner


def _ensure_utf8_stdio() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream and hasattr(stream, "reconfigure"):
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

    def __init__(self, config_path: Optional[str] = None, **overrides: Any):
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

        self.history_dir = self.graph_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # ---- build -----------------------------------------------------------
    def build(self, docs: List[str]) -> None:
        self.runner.build_index(docs)

    def build_from_file(self, path: str) -> None:
        txt = Path(path).read_text(encoding="utf-8", errors="ignore")
        docs = [chunk.strip() for chunk in txt.split("<sep>") if chunk.strip()]
        if not docs:
            docs = [txt]
        self.build(docs)

    # ---- retrieve / answer ----------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        *,
        run_id: Optional[str] = None,
        qid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the structured retrieval context for a query and persist it to history."""
        run_identifier = run_id or self.cfg["run_id"]
        qid_value = qid or self._generate_qid()
        context_payload = self.runner.retrieve(query, top_k=top_k)
        record = self._build_history_record(
            run_id=run_identifier,
            qid=qid_value,
            query=query,
            context_payload=context_payload,
            answer=None,
        )
        self._persist_history(run_identifier, qid_value, record)
        return record

    def answer(
        self,
        query: str,
        top_k: int = 8,
        include_context: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate an answer, persist the exchange to history, and optionally include context."""
        user_wants_context = include_context
        kwargs = dict(kwargs)

        run_identifier = kwargs.pop("run_id", None) or self.cfg["run_id"]
        qid_override = kwargs.pop("qid", None)
        model_override = kwargs.get("model")
        kwargs.pop("include_context", None)

        top_k_used = top_k if top_k is not None else getattr(self.runner, "default_top_k", 8)

        if hasattr(self.runner, "answer"):
            runner_payload = self.runner.answer(query, top_k=top_k, include_context=True, **kwargs)
            context_payload = runner_payload.get("context")
            if context_payload is None:
                context_payload = self.runner.retrieve(query, top_k=top_k_used)
            answer_text = runner_payload.get("answer", "")
            model_name = runner_payload.get("model") or model_override
        else:
            context_payload = self.runner.retrieve(query, top_k=top_k_used)
            answer_text = ""
            model_name = model_override

        qid_value = qid_override or self._generate_qid()
        record = self._build_history_record(
            run_id=run_identifier,
            qid=qid_value,
            query=query,
            context_payload=context_payload,
            answer=answer_text,
        )
        self._persist_history(run_identifier, qid_value, record)

        response: Dict[str, Any] = dict(record)
        if not answer_text:
            response["answer"] = answer_text or ""
        if model_name:
            response.setdefault("metadata", {})
            response["metadata"]["model"] = model_name
        response.setdefault("metadata", {})["top_k"] = top_k_used

        if not user_wants_context:
            response.pop("context", None)
            response.pop("node_hits", None)

        return response

    # ---- history helpers -------------------------------------------------
    def _empty_node_hits(self) -> Dict[str, List[Any]]:
        return {key: [] for key in ("use_communities", "use_reasoning_path", "node_datas", "use_text_units")}

    def _normalise_context_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalised = {"context": "", "node_hits": self._empty_node_hits()}
        if not isinstance(payload, dict):
            return normalised
        normalised["context"] = str(payload.get("context") or "")
        node_hits_src = payload.get("node_hits") if isinstance(payload.get("node_hits"), dict) else {}
        if isinstance(node_hits_src, dict):
            for key in normalised["node_hits"]:
                values = node_hits_src.get(key)
                if isinstance(values, list):
                    normalised["node_hits"][key] = list(values)
        return normalised

    def _generate_qid(self) -> str:
        return f"q_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    def _build_history_record(
        self,
        run_id: str,
        qid: str,
        query: str,
        context_payload: Optional[Dict[str, Any]],
        answer: Optional[str],
    ) -> Dict[str, Any]:
        normalised = self._normalise_context_payload(context_payload)
        node_hits_copy = {key: list(normalised["node_hits"][key]) for key in normalised["node_hits"]}
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "qid": qid,
            "query": query,
            "context": normalised["context"],
            "node_hits": node_hits_copy,
            "answer": answer,
        }

    def _persist_history(self, run_id: str, qid: str, record: Dict[str, Any]) -> None:
        run_dir = self.history_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        out_dir = run_dir / qid
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "context.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- dump index.json -------------------------------------------------
    def dump_index(self, out_path: str) -> None:
        self.runner.dump_index({}, Path(out_path), self.cfg["run_id"])

    # ---- health ----------------------------------------------------------
    def healthy(self) -> bool:
        return self.runner.health_check()
