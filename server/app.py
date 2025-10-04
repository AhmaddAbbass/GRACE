"""Flask application exposing GRACE APIs for knowledge-graph retrieval."""
from __future__ import annotations

import json
import logging
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, request, stream_with_context

from .agent import RankedKG, rank_kgs, summarize_kg
from .config import SETTINGS
from .utils import (
    build_kg_metadata,
    collect_history_items,
    generate_qid,
    generate_run_id,
    get_kg_info,
    get_rag_for_kg,
    list_kgs,
    load_index_payload,
    refresh_registry,
)

LOGGER = logging.getLogger("grace.server")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(code: str, message: str, status: int = 400) -> Response:
    resp = jsonify({"error": {"code": code, "message": message}})
    resp.status_code = status
    return resp


def _success(payload: Any, status: int = 200) -> Response:
    resp = jsonify(payload)
    resp.status_code = status
    return resp


def _require_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return _error("INVALID_CONTENT_TYPE", "Expected application/json body", 415)
        return func(*args, **kwargs)

    return wrapper


def _default_kg_info():
    kgs = list_kgs()
    if not kgs:
        raise RuntimeError("No knowledge graphs available")
    return kgs[0]


def _resolve_kg_info(body: Dict[str, Any]) -> Optional[Any]:
    kg_id = (
        body.get("kg")
        or body.get("kg_id")
        or request.args.get("kg")
        or request.args.get("kg_id")
    )
    if kg_id:
        try:
            return get_kg_info(str(kg_id))
        except KeyError:
            return None
    try:
        return _default_kg_info()
    except RuntimeError:
        return None


def _ui_payload(record: Dict[str, Any], include_answer: bool) -> Dict[str, Any]:
    payload = {
        "qid": record.get("qid"),
        "context": record.get("context", ""),
        "node_hits": record.get("node_hits", {}),
    }
    if include_answer:
        payload["answer"] = record.get("answer") or ""
    return payload


def _ensure_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _flatten_history(run_id: Optional[str] = None, kg: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    records: List[Tuple[str, Dict[str, Any], str]] = []
    infos = []
    if kg:
        try:
            infos = [get_kg_info(kg)]
        except KeyError:
            return []
    else:
        infos = list_kgs()

    for info in infos:
        history_root = info.history_dir
        if not history_root.exists():
            continue
        run_dirs = []
        if run_id:
            candidate = history_root / run_id
            if candidate.exists():
                run_dirs = [candidate]
        else:
            run_dirs = sorted([
                d for d in history_root.iterdir() if d.is_dir()
            ], key=lambda p: p.stat().st_mtime, reverse=True)

        for run_dir in run_dirs:
            for qid_dir in run_dir.iterdir():
                ctx_path = qid_dir / "context.json"
                if not ctx_path.exists():
                    continue
                try:
                    data = json.loads(ctx_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                records.append((info.kg_id, data, run_dir.name))

    records.sort(key=lambda entry: entry[1].get("ts") or "")
    history: List[Dict[str, Any]] = []
    for kg_id, data, run_id_value in records[:limit]:
        history.append(
            {
                "kg_id": kg_id,
                "run_id": run_id_value,
                "qid": data.get("qid"),
                "ts": data.get("ts"),
                "query": data.get("query"),
                "answer": data.get("answer"),
            }
        )
    return history


def _find_context_file(info, qid: str, run_id: Optional[str]) -> Optional[Path]:
    history_root = info.history_dir
    if not history_root.exists():
        return None
    run_dirs = []
    if run_id:
        candidate = history_root / run_id
        run_dirs = [candidate] if candidate.exists() else []
    else:
        run_dirs = sorted([
            d for d in history_root.iterdir() if d.is_dir()
        ], key=lambda p: p.stat().st_mtime, reverse=True)
    for run_dir in run_dirs:
        ctx_path = run_dir / qid / "context.json"
        if ctx_path.exists():
            return ctx_path
    return None


@app.after_request
def _apply_cors(response: Response) -> Response:
    if SETTINGS.app.cors_origins:
        origin = request.headers.get("Origin")
        if "*" in SETTINGS.app.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in SETTINGS.app.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/healthz", methods=["GET"])
def healthz() -> Response:
    return _success({"status": "ok"})


@app.route("/kgs", methods=["GET"])
def list_knowledge_graphs() -> Response:
    if request.args.get("refresh") in {"1", "true", "True"}:
        refresh_registry()
    items = [build_kg_metadata(info) for info in list_kgs()]
    return _success({"items": items, "next_page": None})


@app.route("/kgs/<path:kg_id>/index.json", methods=["GET"])
@app.route("/data/<path:kg_id>", methods=["GET"])
def get_index(kg_id: str) -> Response:
    try:
        info = get_kg_info(kg_id)
    except KeyError:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {kg_id}", 404)

    try:
        payload = load_index_payload(info)
    except FileNotFoundError:
        return _error("INDEX_MISSING", "index.json not available for this KG", 404)

    response = _success(payload)
    try:
        etag = f"W/\"{info.index_path.stat().st_mtime_ns}\""
        response.headers["ETag"] = etag
    except FileNotFoundError:
        pass
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/data/<path:kg_id>/<qid>/context.json", methods=["GET"])
def get_context(kg_id: str, qid: str) -> Response:
    try:
        info = get_kg_info(kg_id)
    except KeyError:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {kg_id}", 404)

    run_id = request.args.get("run_id")
    ctx_path = _find_context_file(info, qid, run_id)
    if not ctx_path:
        return _error("CONTEXT_NOT_FOUND", "Context for the given qid was not found", 404)

    try:
        payload = json.loads(ctx_path.read_text(encoding="utf-8"))
    except Exception:
        return _error("CONTEXT_READ_ERROR", "Failed to read stored context", 500)
    payload.pop("metadata", None)
    payload["kg_id"] = kg_id
    return _success(payload)


@app.route("/retrieve", methods=["POST"])
@_require_json
def retrieve_manual() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return _error("MISSING_QUERY", "'query' is required")

    kg_ids = body.get("kg_ids")
    if isinstance(kg_ids, list) and kg_ids:
        return _retrieve_multi(body, query)

    info = _resolve_kg_info(body)
    if info is None:
        return _error("UNKNOWN_KG", "Unable to resolve knowledge graph", 404)

    run_id = body.get("run_id") or request.args.get("run_id") or "ui_default"
    qid = body.get("qid") or generate_qid()
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)

    rag = get_rag_for_kg(info.kg_id)
    try:
        record = rag.retrieve(query, top_k=top_k, run_id=run_id, qid=qid)
    except Exception as exc:
        LOGGER.exception("Retrieve failed for %s", info.kg_id, exc_info=exc)
        return _error("RETRIEVE_FAILED", f"Failed to retrieve from {info.kg_id}", 500)

    payload = _ui_payload(record, include_answer=False)
    payload["kg_id"] = info.kg_id
    payload["run_id"] = record.get("run_id", run_id)
    return _success(payload)


@app.route("/answer", methods=["POST"])
@_require_json
def answer_manual() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return _error("MISSING_QUERY", "'query' is required")

    kg_ids = body.get("kg_ids")
    if isinstance(kg_ids, list) and kg_ids:
        return _answer_multi(body, query)

    info = _resolve_kg_info(body)
    if info is None:
        return _error("UNKNOWN_KG", "Unable to resolve knowledge graph", 404)

    run_id = body.get("run_id") or request.args.get("run_id") or "ui_default"
    qid = body.get("qid") or generate_qid()
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    model = body.get("model")
    system_prompt = body.get("system_prompt")

    kwargs: Dict[str, Any] = {}
    if model:
        kwargs["model"] = model
    if system_prompt:
        kwargs["system_prompt"] = system_prompt

    rag = get_rag_for_kg(info.kg_id)
    try:
        record = rag.answer(
            query,
            top_k=top_k,
            include_context=True,
            run_id=run_id,
            qid=qid,
            **kwargs,
        )
    except Exception as exc:
        LOGGER.exception("Answer failed for %s", info.kg_id, exc_info=exc)
        return _error("ANSWER_FAILED", f"Failed to generate answer for {info.kg_id}", 500)

    payload = _ui_payload(record, include_answer=True)
    payload["kg_id"] = info.kg_id
    payload["run_id"] = record.get("run_id", run_id)
    return _success(payload)


def _prepare_payload(payload: Dict[str, Any], *, include_answer: bool) -> Dict[str, Any]:
    clean = dict(payload)
    if not include_answer:
        clean.pop("answer", None)
    clean.pop("metadata", None)
    if include_answer and not clean.get("answer"):
        clean["answer"] = "No evidence found."
    if not clean.get("context"):
        clean.setdefault("context", "")
    return clean


def _retrieve_multi(body: Dict[str, Any], query: str) -> Response:
    kg_ids = body.get("kg_ids") or []
    try:
        infos = [get_kg_info(str(kg_id)) for kg_id in kg_ids]
    except KeyError as exc:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {exc.args[0]}", 404)

    run_id = generate_run_id(body.get("run_id"))
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    qid = generate_qid()

    results: List[Dict[str, Any]] = []
    for info in infos:
        rag = get_rag_for_kg(info.kg_id)
        try:
            payload = rag.retrieve(query, top_k=top_k, run_id=run_id, qid=qid)
        except Exception as exc:
            LOGGER.exception("Retrieve failed for %s", info.kg_id, exc_info=exc)
            return _error("RETRIEVE_FAILED", f"Failed to retrieve from {info.kg_id}", 500)
        results.append({"kg_id": info.kg_id, "payload": _prepare_payload(payload, include_answer=False)})

    return _success({"run_id": run_id, "qid": qid, "query": query, "results": results})


def _answer_multi(body: Dict[str, Any], query: str) -> Response:
    kg_ids = body.get("kg_ids") or []
    try:
        infos = [get_kg_info(str(kg_id)) for kg_id in kg_ids]
    except KeyError as exc:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {exc.args[0]}", 404)

    run_id = generate_run_id(body.get("run_id"))
    qid = generate_qid()
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    model = body.get("model")
    system_prompt = body.get("system_prompt")

    kwargs: Dict[str, Any] = {}
    if model:
        kwargs["model"] = model
    if system_prompt:
        kwargs["system_prompt"] = system_prompt

    results: List[Dict[str, Any]] = []
    for info in infos:
        rag = get_rag_for_kg(info.kg_id)
        try:
            payload = rag.answer(
                query,
                top_k=top_k,
                include_context=True,
                run_id=run_id,
                qid=qid,
                **kwargs,
            )
        except Exception as exc:
            LOGGER.exception("Answer failed for %s", info.kg_id, exc_info=exc)
            return _error("ANSWER_FAILED", f"Failed to generate answer for {info.kg_id}", 500)
        results.append({"kg_id": info.kg_id, "payload": _prepare_payload(payload, include_answer=True)})

    return _success({"run_id": run_id, "qid": qid, "query": query, "results": results})


# ---------------------------------------------------------------------------
# Auto-routing endpoints (unchanged)
# ---------------------------------------------------------------------------

def _rank_and_select(query: str, top_m: int) -> List[RankedKG]:
    infos = list_kgs()
    if not infos:
        return []
    ranked = rank_kgs(query, infos, top_m=top_m)
    return ranked


@app.route("/retrieve/auto", methods=["POST"])
@_require_json
def retrieve_auto() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return _error("MISSING_QUERY", "'query' is required")

    run_id = generate_run_id(body.get("run_id"))
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    top_m = _ensure_positive_int(body.get("top_m"), SETTINGS.default_top_m)
    qid = generate_qid()

    ranked = _rank_and_select(query, top_m)
    if not ranked:
        return _error("NO_KGS", "No knowledge graphs available", 404)

    results: List[Dict[str, Any]] = []
    for entry in ranked:
        rag = get_rag_for_kg(entry.info.kg_id)
        try:
            payload = rag.retrieve(query, top_k=top_k, run_id=run_id, qid=qid)
        except Exception as exc:
            LOGGER.exception("Auto retrieve failed for %s", entry.info.kg_id, exc_info=exc)
            return _error("RETRIEVE_FAILED", f"Failed to retrieve from {entry.info.kg_id}", 500)
        results.append({"kg_id": entry.info.kg_id, "payload": _prepare_payload(payload, include_answer=False)})

    rankings_payload = [
        {"kg_id": entry.info.kg_id, "score": round(entry.score, 3)}
        for entry in ranked
    ]

    return _success({
        "run_id": run_id,
        "qid": qid,
        "query": query,
        "kg_rankings": rankings_payload,
        "results": results,
    })


@app.route("/answer/auto", methods=["POST"])
@_require_json
def answer_auto() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return _error("MISSING_QUERY", "'query' is required")

    run_id = generate_run_id(body.get("run_id"))
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    top_m = _ensure_positive_int(body.get("top_m"), SETTINGS.default_top_m)
    qid = generate_qid()
    model = body.get("model")
    system_prompt = body.get("system_prompt")

    ranked = _rank_and_select(query, top_m)
    if not ranked:
        return _error("NO_KGS", "No knowledge graphs available", 404)

    kwargs: Dict[str, Any] = {}
    if model:
        kwargs["model"] = model
    if system_prompt:
        kwargs["system_prompt"] = system_prompt

    results: List[Dict[str, Any]] = []
    for entry in ranked:
        rag = get_rag_for_kg(entry.info.kg_id)
        try:
            payload = rag.answer(
                query,
                top_k=top_k,
                include_context=True,
                run_id=run_id,
                qid=qid,
                **kwargs,
            )
        except Exception as exc:
            LOGGER.exception("Auto answer failed for %s", entry.info.kg_id, exc_info=exc)
            return _error("ANSWER_FAILED", f"Failed to answer using {entry.info.kg_id}", 500)
        results.append({"kg_id": entry.info.kg_id, "payload": _prepare_payload(payload, include_answer=True)})

    rankings_payload = [
        {"kg_id": entry.info.kg_id, "score": round(entry.score, 3)}
        for entry in ranked
    ]

    return _success({
        "run_id": run_id,
        "qid": qid,
        "query": query,
        "kg_rankings": rankings_payload,
        "results": results,
    })


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.route("/history", methods=["GET"])
def get_history() -> Response:
    run_id = request.args.get("run_id")
    limit = _ensure_positive_int(request.args.get("limit"), 50)
    before_qid = request.args.get("before_qid")
    kg = request.args.get("kg") or request.args.get("kg_id")

    if run_id:
        items, next_page = collect_history_items(run_id, limit, before_qid)
        for item in items:
            payload = item.get("payload") or {}
            payload.pop("metadata", None)
        return _success({"run_id": run_id, "items": items, "next_page": next_page})

    records = _flatten_history(run_id=None, kg=kg, limit=limit)
    return _success(records)


@app.route("/summaries/refresh", methods=["POST"])
@_require_json
def refresh_summary() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    kg_id = str(body.get("kg_id") or "").strip()
    if not kg_id:
        return _error("MISSING_KG_ID", "'kg_id' is required")
    force = bool(body.get("force", False))

    try:
        info = get_kg_info(kg_id)
    except KeyError:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {kg_id}", 404)

    try:
        summarize_kg(info, force=force)
    except Exception as exc:
        LOGGER.exception("Summary refresh failed for %s", kg_id, exc_info=exc)
        return _success({"kg_id": kg_id, "status": "failed"}, status=500)

    return _success({"kg_id": kg_id, "status": "done"})


# ---------------------------------------------------------------------------
# Streaming answer (unchanged)
# ---------------------------------------------------------------------------

def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route("/answer/stream", methods=["POST"])
@_require_json
def answer_stream() -> Response:
    body: Dict[str, Any] = request.get_json() or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return _error("MISSING_QUERY", "'query' is required")

    kg_ids = body.get("kg_ids") or []
    if not isinstance(kg_ids, list) or len(kg_ids) != 1:
        return _error("INVALID_KG_IDS", "Streaming endpoint requires exactly one kg_id")

    kg_id = str(kg_ids[0])
    try:
        info = get_kg_info(kg_id)
    except KeyError:
        return _error("UNKNOWN_KG", f"Knowledge graph not found: {kg_id}", 404)

    run_id = generate_run_id(body.get("run_id"))
    qid = generate_qid()
    top_k = _ensure_positive_int(body.get("top_k"), SETTINGS.default_top_k)
    model = body.get("model")
    system_prompt = body.get("system_prompt")

    kwargs: Dict[str, Any] = {}
    if model:
        kwargs["model"] = model
    if system_prompt:
        kwargs["system_prompt"] = system_prompt

    rag = get_rag_for_kg(info.kg_id)

    def generate():
        try:
            yield _sse_event("context_progress", {"phase": "retrieval", "progress": 0.0})
            context_payload = rag.retrieve(query, top_k=top_k, run_id=run_id, qid=qid)
            yield _sse_event("context_progress", {"phase": "retrieval", "progress": 1.0})
            answer_payload = rag.answer(
                query,
                top_k=top_k,
                include_context=True,
                run_id=run_id,
                qid=qid,
                **kwargs,
            )
            prepared = _prepare_payload(answer_payload, include_answer=True)
            yield _sse_event("answer", {"run_id": run_id, "qid": qid, "kg_id": kg_id, "delta": prepared.get("answer", "")})
            yield _sse_event("done", {"run_id": run_id, "kg_id": kg_id, "qid": qid, "payload": prepared})
        except Exception as exc:
            LOGGER.exception("Streaming answer failed", exc_info=exc)
            yield _sse_event("error", {"code": "SERVER_ERROR", "message": str(exc)})

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=8000, debug=False)
