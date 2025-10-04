"""Minimal Flask gateway wrapping the GRACE RAG toolkit."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parent
if __package__ in (None, ""):
    sys.path.append(str(ROOT))
    sys.path.append(str(ROOT.parent))
    from utils import (  # type: ignore
        build_health_payload,
        get_logger,
        load_config,
        make_rag,
        summarise_text_units,
    )
else:  # pragma: no cover
    from .utils import build_health_payload, get_logger, load_config, make_rag, summarise_text_units

cfg = load_config()
logger = get_logger()
rag_cfg = cfg.get("rag", {}) or {}

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health() -> Any:
    payload = build_health_payload()
    status = 200 if payload.get("rag") else 503
    return jsonify({"status": "ok" if status == 200 else "degraded", **payload}), status


@app.route("/config", methods=["GET"])
def show_config() -> Any:
    redacted = {**cfg}
    return jsonify(redacted)


@app.route("/chat", methods=["POST"])
def chat() -> Any:
    body: Dict[str, Any] = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "'query' is required"}), 400

    top_k = int(body.get("top_k") or rag_cfg.get("answer_top_k") or rag_cfg.get("retrieve_top_k") or 6)
    include_context = bool(rag_cfg.get("include_context", True))
    allow_answer = bool(body.get("force_context_only") is None and rag_cfg.get("answer_top_k"))

    rag = make_rag()

    logger.info("[chat] query='%s' top_k=%s", query, top_k)
    context = rag.retrieve(query, top_k=top_k)

    response: Dict[str, Any] = {
        "query": query,
        "context": context if include_context else None,
        "snippets": summarise_text_units(context.get("use_text_units") or []),
    }

    if allow_answer:
        try:
            answer_payload = rag.answer(query, top_k=top_k, include_context=False)
            response["answer"] = answer_payload.get("answer")
        except Exception as exc:  # pragma: no cover - runtime only
            logger.exception("Failed to run rag.answer: %s", exc)
            response["answer_error"] = str(exc)

    return jsonify(response)


@app.route("/context", methods=["GET"])
def context() -> Any:
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query parameter is required"}), 400
    top_k = int(request.args.get("top_k") or rag_cfg.get("retrieve_top_k") or 6)
    rag = make_rag()
    ctx = rag.retrieve(query, top_k=top_k)
    return jsonify({
        "query": query,
        "context": ctx,
        "snippets": summarise_text_units(ctx.get("use_text_units") or []),
    })


if __name__ == "__main__":  # pragma: no cover
    host = cfg.get("app", {}).get("host", "0.0.0.0")
    port = int(cfg.get("app", {}).get("port", 8000))
    debug = bool(cfg.get("app", {}).get("debug", False))
    app.run(host=host, port=port, debug=debug)
