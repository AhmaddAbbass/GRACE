# rag/runners/hirag.py
from pathlib import Path
import json, logging, csv, io, re
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
from openai import OpenAI

from .base import BaseRagRunner

# HiRAG import (try a couple of common layouts)
try:
    from HiRAG.hirag.hirag import HiRAG, QueryParam
except Exception:
    try:
        from hirag.hirag import HiRAG, QueryParam
    except Exception as e:
        raise ImportError(
            "Could not import HiRAG. Please add it to your environment "
            "(e.g. `pip install HiRAG` or ensure its path is importable)."
        ) from e

# Optional fast prefix matching (we don't strictly need it here)
try:
    from marisa_trie import Trie
except ImportError:
    Trie = None

CHUNK_SPLIT = re.compile(r"--New Chunk--\n")

DEFAULT_ANSWER_MODEL = 'gpt-4o-mini'
DEFAULT_ANSWER_SYSTEM_PROMPT = (
    'You are a careful assistant that answers questions using only the supplied context. ' +
    'Synthesize the most relevant details, cite the context explicitly when possible, and explain reasoning succinctly. ' +
    'If the context truly lacks the answer, explicitly say so, but do not default to that response when partial clues exist.'
)

class HiRAGRunner(BaseRagRunner):
    def __init__(
        self,
        workdir: Path,
        *,
        mode: str = "hi",
        run_id: str,
        cache_dir: Path,
        embedding_func,
        enable_naive_rag: bool = True,
        chunk_prefix_len: int = 120,
        log_level: int = logging.INFO,
        node_hit_strategy: str = "union",
        **kwargs
    ):
        super().__init__(workdir, **kwargs)
        self.mode      = mode
        self.run_id    = run_id
        self.cache_dir = cache_dir
        self.chunk_prefix_len = chunk_prefix_len
        self.node_hit_strategy = node_hit_strategy

        self.answer_model = kwargs.pop("answer_model", DEFAULT_ANSWER_MODEL)
        self.answer_system_prompt = kwargs.pop("answer_system_prompt", DEFAULT_ANSWER_SYSTEM_PROMPT)
        self._chat_client: Optional[OpenAI] = None

        # simple logger to file
        self.logger = logging.getLogger(f"HiRAGRunner-{mode}-{run_id}")
        self.logger.setLevel(log_level)
        self.workdir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(self.workdir / "debug_hi.log"))
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        self.logger.addHandler(fh)

        self.logger.info(f"[INIT] HiRAGRunner mode={mode} run_id={run_id}")
        self.logger.info(f"[INIT] Embedding func = {type(embedding_func).__name__}")

        # Build HiRAG core
        hirag_kwargs = dict(
            working_dir=str(self.cache_dir),
            enable_naive_rag=enable_naive_rag,
            embedding_func=embedding_func,
            **{k: kwargs[k] for k in (
                "chunk_func","chunk_token_size","chunk_overlap_token_size",
                "tiktoken_model_name","graph_cluster_algorithm","max_graph_cluster_size",
                "graph_cluster_seed","node_embedding_algorithm","node2vec_params",
                "enable_hierachical_mode","special_community_report_llm_kwargs",
                "embedding_batch_num","embedding_func_max_async",
                "query_better_than_threshold","using_azure_openai",
                "enable_llm_cache"
            ) if k in kwargs}
        )
        self._rag = HiRAG(**hirag_kwargs)

        self._load_chunk_index()

    # ---------- internal helpers ----------
    def _load_chunk_index(self):
        kv = self.cache_dir / "kv_store_text_chunks.json"
        self._id_by_text_head: Dict[str,str] = {}
        self._id_by_full: Dict[str,str] = {}
        self._trie = None

        if kv.exists():
            data = json.loads(kv.read_text(encoding="utf-8"))
            self._id_by_text_head = {
                v["content"][:self.chunk_prefix_len]: k
                for k,v in data.items()
            }
            self._id_by_full = {v["content"]:k for k,v in data.items()}
            self.logger.info(f"[INIT] KV-store loaded {len(self._id_by_full)} chunks")
            if Trie and self._id_by_text_head:
                self._trie = Trie(self._id_by_text_head.keys())
        else:
            self.logger.warning("[INIT] KV-store missing; run build_index")

    def _extract_csv_section(self, text: str, section: str) -> Optional[str]:
        marker = f"-----{section}-----"
        if marker not in text:
            return None
        part = text.split(marker, 1)[1]
        idx = part.find("```csv")
        if idx < 0:
            return None
        part = part[idx + len("```csv"):]
        if part.startswith("\n"): part = part[1:]
        csv_body, *_ = part.split("```", 1)
        return csv_body.strip()

    # robust CSV→DataFrame even with stray commas
    def _parse_df(self, csv_text: str) -> pd.DataFrame:
        if not csv_text or not csv_text.strip():
            return pd.DataFrame()
        txt = csv_text.replace(",\t", ",")
        txt = re.sub(r'"\s*<SEP>\s*"', ' ', txt)
        txt = txt.replace("<SEP>", " ")
        buf = io.StringIO(txt)
        reader = csv.reader(buf, quotechar='"', skipinitialspace=True)
        try:
            header = next(reader)
        except StopIteration:
            return pd.DataFrame()
        rows = []
        for row in reader:
            if not row: continue
            if len(row) > len(header):
                fixed = row[: len(header) - 1] + [",".join(row[len(header) - 1 :])]
                rows.append(fixed)
            else:
                rows.append(row)
        return pd.DataFrame(rows, columns=header)

    # ---------- public API ----------
    def retrieve(self, query: str, *, top_k: int = 8):
        self.logger.info(f"[retrieve] {query!r} top_k={top_k}")
        param = QueryParam(mode=self.mode, only_need_context=True, top_k=top_k)
        result = self._rag.query(query, param)
        empty_payload = {
            "use_communities":    [],
            "use_reasoning_path": [],
            "node_datas":         [],
            "use_text_units":     [],
        }
        if not result:
            self.logger.info("[retrieve] no results returned")
            return empty_payload

        result_str = result if isinstance(result, str) else "\n".join(result)

        def _extract(section: str) -> str:
            return self._extract_csv_section(result_str, section) or ""

        comm_df = self._parse_df(_extract("Backgrounds"))
        path_df = self._parse_df(_extract("Reasoning Path"))
        ent_df = self._parse_df(_extract("Detail Entity Information"))
        src_df = self._parse_df(_extract("Source Documents"))

        for col in ("id", "rank"):
            if col in comm_df:
                comm_df[col] = pd.to_numeric(comm_df[col], errors="coerce").fillna(0).astype(int)
        if "weight" in path_df:
            path_df["weight"] = pd.to_numeric(path_df["weight"], errors="coerce").fillna(0.0)
        if "rank" in ent_df:
            ent_df["rank"] = pd.to_numeric(ent_df["rank"], errors="coerce").fillna(0).astype(int)
        if "id" in src_df:
            src_df["id"] = pd.to_numeric(src_df["id"], errors="coerce").fillna(0).astype(int)

        use_communities = (
            comm_df.rename(columns={"content": "report_string"})[["id", "report_string"]]
            .to_dict("records")
            if not comm_df.empty else []
        )

        use_reasoning_path = [
            {
                "src_tgt": (row.get("source", ""), row.get("target", "")),
                "description": row.get("description", ""),
                "weight": row.get("weight", 0.0),
            }
            for _, row in path_df.iterrows()
        ] if not path_df.empty else []

        node_datas = (
            ent_df.rename(columns={"entity": "entity_name", "type": "entity_type"})[["entity_name", "entity_type", "description", "rank"]]
            .to_dict("records")
            if not ent_df.empty else []
        )

        use_text_units = (
            src_df[["id", "content"]].to_dict("records")
            if not src_df.empty else []
        )

        parsed = {
            "use_communities":    use_communities,
            "use_reasoning_path": use_reasoning_path,
            "node_datas":         node_datas,
            "use_text_units":     use_text_units,
        }

        self.logger.info(
            f"[retrieve] parsed communities={len(use_communities)}, "
            f"path={len(use_reasoning_path)}, entities={len(node_datas)}, "
            f"text_units={len(use_text_units)}"
        )
        return parsed

    def build_index(self, docs: List[str]):
        self.logger.info(f"[build_index] inserting {len(docs)} docs")
        original_has_attr = hasattr(self._rag, "enable_hierachical_mode")
        original_hier_mode = getattr(self._rag, "enable_hierachical_mode", None) if original_has_attr else None
        disable_for_small_batch = bool(original_hier_mode) and len(docs) < 3
        if disable_for_small_batch:
            self.logger.info("[build_index] disabling hierarchical mode for small batch")
            self._rag.enable_hierachical_mode = False
        try:
            self._rag.insert(docs)
        except ValueError as exc:
            message = str(exc)
            if (
                "n_components must be greater than 0" in message
                and original_has_attr
                and bool(original_hier_mode)
                and not disable_for_small_batch
            ):
                self.logger.warning(
                    "[build_index] hierarchical clustering failed (%s); retrying with hierarchical mode disabled",
                    message,
                )
                self._rag.enable_hierachical_mode = False
                self._rag.insert(docs)
            else:
                raise
        finally:
            if original_has_attr:
                self._rag.enable_hierachical_mode = original_hier_mode
        self._load_chunk_index()

    def _context_to_prompt(self, context: Dict[str, Any]) -> str:
        blocks: List[str] = []

        text_units = context.get("use_text_units") or []
        for idx, unit in enumerate(text_units, 1):
            content = (unit or {}).get("content", "").strip()
            if content:
                blocks.append(f"[Source {idx}] {content}")

        summaries = [
            (community or {}).get("report_string", "").strip()
            for community in (context.get("use_communities") or [])
        ]
        summaries = [s for s in summaries if s]
        if summaries:
            blocks.append("Community summaries:\n" + "\n".join(summaries))

        reasoning = context.get("use_reasoning_path") or []
        if reasoning:
            lines: List[str] = []
            for hop in reasoning:
                src, tgt = hop.get("src_tgt", ("", ""))
                desc = hop.get("description", "")
                lines.append(f"- {src} -> {tgt}: {desc}")
            if lines:
                blocks.append("Reasoning path:\n" + "\n".join(lines))

        return "\n\n".join(blocks).strip()

    def _get_chat_client(self) -> OpenAI:
        if self._chat_client is None:
            self._chat_client = OpenAI()
        return self._chat_client

    def answer(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        include_context: bool = True,
    ) -> Dict[str, Any]:
        top_k_value = top_k or getattr(self, "default_top_k", 8)
        context = self.retrieve(query, top_k=top_k_value)

        has_context = any(
            bool(context.get(key))
            for key in ("use_text_units", "use_communities", "use_reasoning_path", "node_datas")
        )
        context_prompt = self._context_to_prompt(context) if has_context else ""

        response: Dict[str, Any] = {
            "model": model or self.answer_model,
            "top_k": top_k_value,
        }
        if include_context:
            response["context"] = context

        if not context_prompt:
            response["answer"] = "I do not know. The retrieval index did not provide supporting context."
            return response

        used_model = model or self.answer_model
        system_message = system_prompt or self.answer_system_prompt

        user_prompt_lines = [
            "You are answering a user question using retrieved context.",
            "Use only the provided information; synthesise multiple snippets when useful.",
            "If the context truly lacks the answer, reply: 'The provided context does not cover this.'",
            "",
            "Context:",
            "```",
            context_prompt,
            "```",
            "",
            f"Question: {query}",
        ]
        user_prompt = "\n".join(user_prompt_lines)

        client = self._get_chat_client()
        completion = client.chat.completions.create(
            model=used_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer_text = completion.choices[0].message.content.strip() if completion.choices else ""
        response["answer"] = answer_text or "(empty response)"
        response["model"] = used_model
        return response


    def dump_index(self, qid_hits, out_path: Path, run_id: str):
        from ..vis.index_utils import build_index_payload
        payload = build_index_payload(self.cache_dir, qid_hits, run_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def health_check(self) -> bool:
        try:
            return (
                (self.cache_dir / "kv_store_text_chunks.json").exists() and
                (self.cache_dir / "graph_chunk_entity_relation.graphml").exists()
            )
        except Exception:
            return False



