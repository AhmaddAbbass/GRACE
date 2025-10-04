"""Agent helpers: KG summarisation and ranking using an LLM."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Sequence, Tuple

from openai import OpenAI

from .config import SETTINGS
from .utils import KGInfo, load_chunk_samples

LOGGER = logging.getLogger("grace.server.agent")


@dataclass(frozen=True)
class RankedKG:
    info: KGInfo
    score: float


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    return OpenAI()


def summarize_kg(info: KGInfo, *, force: bool = False) -> str:
    if info.summary_path.exists() and not force:
        return info.summary_path.read_text(encoding="utf-8").strip()

    samples = load_chunk_samples(info, SETTINGS.summary.max_chunks, SETTINGS.summary.max_chars_per_chunk)
    if not samples:
        summary = "No source excerpts were available for this knowledge graph."
        info.summary_path.parent.mkdir(parents=True, exist_ok=True)
        info.summary_path.write_text(summary, encoding="utf-8")
        return summary

    client = _get_client()
    user_lines = [
        f"Knowledge graph: {info.kg_id}",
        f"Graph directory: {info.graph_dir}",
        "",
        "Sample excerpts:",
    ]
    for idx, chunk in enumerate(samples, 1):
        user_lines.append(f"[{idx}] {chunk}")

    try:
        completion = client.chat.completions.create(
            model=SETTINGS.summary.model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SETTINGS.summary.prompt},
                {"role": "user", "content": "\n".join(user_lines)},
            ],
        )
        summary = completion.choices[0].message.content.strip() if completion.choices else ""
    except Exception as exc:  # pragma: no cover - network/runtime
        LOGGER.warning("Failed to summarise %s: %s", info.kg_id, exc)
        summary = "Summary unavailable due to LLM error."

    if not summary:
        summary = "Summary unavailable."

    info.summary_path.parent.mkdir(parents=True, exist_ok=True)
    info.summary_path.write_text(summary, encoding="utf-8")
    return summary


def _parse_rankings(response_text: str, available_ids: List[str]) -> List[Tuple[str, float]]:
    try:
        data = json.loads(response_text)
        if isinstance(data, list):
            rankings: List[Tuple[str, float]] = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                kg_id = entry.get("kg_id")
                score = entry.get("score", 0.0)
                if isinstance(kg_id, str) and kg_id in available_ids:
                    try:
                        score_value = float(score)
                    except (TypeError, ValueError):
                        score_value = 0.0
                    rankings.append((kg_id, score_value))
            return rankings
    except json.JSONDecodeError:
        pass

    # fallback: attempt to extract JSON array substring
    try:
        start = response_text.index("[")
        end = response_text.rindex("]") + 1
        snippet = response_text[start:end]
        data = json.loads(snippet)
        if isinstance(data, list):
            rankings: List[Tuple[str, float]] = []
            for entry in data:
                if isinstance(entry, dict):
                    kg_id = entry.get("kg_id")
                    score = entry.get("score", 0.0)
                    if isinstance(kg_id, str) and kg_id in available_ids:
                        try:
                            score_value = float(score)
                        except (TypeError, ValueError):
                            score_value = 0.0
                        rankings.append((kg_id, score_value))
            if rankings:
                return rankings
    except (ValueError, json.JSONDecodeError):
        pass

    return []


def rank_kgs(query: str, kg_infos: Sequence[KGInfo], *, top_m: int) -> List[RankedKG]:
    if top_m <= 0 or not kg_infos:
        return []

    available_ids = [info.kg_id for info in kg_infos]
    client = _get_client()

    descriptions = []
    for info in kg_infos:
        summary = summarize_kg(info)
        descriptions.append({"kg_id": info.kg_id, "summary": summary, "path": str(info.graph_dir)})

    request_payload = {
        "query": query,
        "knowledge_graphs": descriptions,
        "instructions": "Return a JSON array of objects with kg_id and score (0-1). Include only the most relevant graphs."
    }

    try:
        completion = client.chat.completions.create(
            model=SETTINGS.summary.model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You rank knowledge graphs for answering the user's query. "
                        "Respond ONLY with a JSON array: [{\"kg_id\": str, \"score\": float between 0 and 1}, ...]."
                    ),
                },
                {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)},
            ],
        )
        response_text = completion.choices[0].message.content if completion.choices else ""
    except Exception as exc:  # pragma: no cover - network/runtime
        LOGGER.warning("Failed to rank KGs: %s", exc)
        response_text = ""

    rankings = _parse_rankings(response_text or "", available_ids)

    if not rankings:
        step = 1.0 / max(len(available_ids), 1)
        rankings = [(kg_id, max(0.0, 1.0 - idx * step)) for idx, kg_id in enumerate(available_ids)]

    ranked: List[RankedKG] = []
    seen = set()
    for kg_id, score in rankings:
        if kg_id in seen:
            continue
        seen.add(kg_id)
        try:
            info = next(info for info in kg_infos if info.kg_id == kg_id)
        except StopIteration:
            continue
        ranked.append(RankedKG(info=info, score=float(score)))
        if len(ranked) >= top_m:
            break

    if len(ranked) < top_m:
        for info in kg_infos:
            if info.kg_id in seen:
                continue
            ranked.append(RankedKG(info=info, score=0.0))
            if len(ranked) >= top_m:
                break

    return ranked


__all__ = ["RankedKG", "summarize_kg", "rank_kgs"]
