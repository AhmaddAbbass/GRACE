# rag/vis/index_utils.py
#!/usr/bin/env python3
from __future__ import annotations
import json, ast, re, datetime, pathlib
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Set
import networkx as nx

def read_json(p: pathlib.Path) -> Dict[str, Any]:
    return json.loads(p.read_text("utf-8")) if p.exists() else {}

def read_graphml(p: pathlib.Path) -> nx.Graph:
    return nx.read_graphml(p) if p.exists() else nx.Graph()

_RE_CSV = re.compile(r'"?(.*?)"?,\s*"?([^,]+)"?,\s*"?([^,]+)"?')

def csv_edges(block: str) -> Set[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()
    for ln in block.splitlines():
        m = _RE_CSV.match(ln)
        if m:
            out.add(tuple(sorted((m.group(2), m.group(3)))))
    return out

def parse_clusters(raw: str) -> List[Dict[str, Any]]:
    txt = (raw or "").strip()
    if not txt: return []
    if (txt.startswith('"') and txt.endswith('"')) or (txt.startswith("'") and txt.endswith("'")):
        txt = txt[1:-1]
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(txt)
        except Exception:
            return []

def build_index_payload(
    cache_dir: pathlib.Path,
    qid_hits: Dict[str, List[str]],
    run_id: str,
) -> Dict[str, Any]:
    chunks = read_json(cache_dir / "kv_store_text_chunks.json")
    G = read_graphml(cache_dir / "graph_chunk_entity_relation.graphml")

    deg = dict(G.degree())
    n = G.number_of_nodes()
    btw = (
        nx.betweenness_centrality(G)
        if n <= 50
        else nx.betweenness_centrality(G, k=min(300, max(10, n // 5)))
    )

    hit_set: Set[str] = set().union(*qid_hits.values()) if qid_hits else set()

    entity_to_sources = {
        nid: (meta.get("source_id", "")).split("<SEP>")
        if meta.get("source_id")
        else []
        for nid, meta in G.nodes(data=True)
    }

    nodes: List[Dict[str, Any]] = []
    for nid, meta in G.nodes(data=True):
        parsed = parse_clusters(meta.get("clusters", "[]")) if meta.get("clusters") else []
        level = max((int(c.get("level", 0)) for c in parsed), default=0)
        cluster = next((c.get("cluster") for c in parsed if int(c.get("level", 0)) == level), None)

        tags: List[str] = []
        if nid in hit_set:
            tags.append("retrieval_hit")
        elif any(sid in hit_set for sid in entity_to_sources.get(nid, [])):
            tags.append("retrieval_source")

        nodes.append(
            {
                "id": nid,
                "label": str(nid).strip('"'),
                "kind": (meta.get("entity_type") or meta.get("kind") or "entity").lower(),
                "level": level,
                "degree": deg.get(nid, 0),
                "betweenness": round(btw.get(nid, 0), 6),
                "cluster": cluster,
                "cluster_size": None,
                "tags": tags,
                "saved_pos": None,
                "source_ids": entity_to_sources.get(nid, []),
                **meta,
            }
        )

    c_sizes: Dict[Any, int] = defaultdict(int)
    for nobj in nodes:
        if nobj["cluster"] is not None:
            c_sizes[nobj["cluster"]] += 1
    for nobj in nodes:
        if nobj["cluster"] is not None:
            nobj["cluster_size"] = c_sizes[nobj["cluster"]]

    cluster_of = {n["id"]: n["cluster"] for n in nodes}
    edges: List[Dict[str, Any]] = []
    for u, v, meta in G.edges(data=True):
        etype = "contains" if meta.get("description", "").startswith("Contains") else "intra"
        if cluster_of.get(u) not in (None, cluster_of.get(v)):
            pass
        else:
            etype = "bridge"

        edges.append(
            {"source": u, "target": v, "weight": meta.get("weight", 1.0), "edge_type": etype, **meta}
        )

    return {
        "metadata": {"run_id": run_id, "ts": datetime.datetime.utcnow().isoformat()},
        "chunks": chunks,
        "entity_graph": {"nodes": nodes, "edges": edges},
    }
