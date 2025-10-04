"""Create a trimmed index.json while preserving the full copy."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from rag import RAG


def _kg_id_from_path(kg_dir: Path) -> str:
    parts = kg_dir.parts
    if len(parts) >= 2:
        return '/'.join(parts[-2:])
    return kg_dir.name


def _clean(text: str | None) -> str:
    if not text:
        return ''
    return text.strip().strip('"')


def _parse_clusters(raw: str | None) -> Tuple[int, int, str]:
    if not raw:
        return 0, 0, '[]'
    raw_clean = raw.strip()
    try:
        clusters = json.loads(raw_clean)
        if isinstance(clusters, list) and clusters:
            first = clusters[0]
            level = int(first.get('level', 0))
            cluster = int(first.get('cluster', 0))
        else:
            level = cluster = 0
    except Exception:
        level = cluster = 0
    return level, cluster, raw_clean


def extract_graph_data(graph_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    graph = nx.read_graphml(graph_path)

    node_records: List[Dict[str, Any]] = []
    cluster_counts: Dict[Tuple[int, int], int] = {}
    for node_id, attrs in graph.nodes(data=True):
        clean_id = _clean(node_id)
        entity_type = _clean(attrs.get('entity_type'))
        description = attrs.get('description') or ''
        source_field = attrs.get('source_id') or ''
        source_ids = [s for s in source_field.split('<SEP>') if s]
        level, cluster, clusters_raw = _parse_clusters(attrs.get('clusters'))
        cluster_counts[(level, cluster)] = cluster_counts.get((level, cluster), 0) + 1
        node_records.append({
            'id': clean_id,
            'label': clean_id,
            'kind': entity_type or 'NODE',
            'level': level,
            'degree': 0,  # placeholder, filled below
            'betweenness': 0.0,
            'cluster': cluster,
            'cluster_size': 0,  # placeholder, filled below
            'tags': [],
            'saved_pos': None,
            'source_ids': source_ids,
            'entity_type': entity_type,
            'description': description,
            'source_id': source_ids[0] if source_ids else '',
            'clusters': clusters_raw,
        })

    degrees = dict(graph.degree())
    for record in node_records:
        record['degree'] = int(degrees.get(record['id'], 0))
        key = (record['level'], record['cluster'])
        record['cluster_size'] = cluster_counts.get(key, 0)

    edge_records: List[Dict[str, Any]] = []
    for u, v, attrs in graph.edges(data=True):
        description = attrs.get('description') or ''
        source_id = attrs.get('source_id') or ''
        order = attrs.get('order')
        weight = attrs.get('weight')
        try:
            weight_f = float(weight) if weight is not None else 1.0
        except Exception:
            weight_f = 1.0
        try:
            order_i = int(order) if order is not None else 0
        except Exception:
            order_i = 0
        edge_records.append({
            'source': _clean(u),
            'target': _clean(v),
            'weight': weight_f,
            'edge_type': attrs.get('edge_type') or 'relation',
            'tags': [],
            'description': description,
            'source_id': source_id,
            'order': order_i,
        })

    return node_records, edge_records


def dump_full_index(kg_dir: Path, config: str, run_id: str, regenerate: bool) -> Dict[str, Any]:
    full_dir = kg_dir / 'full_index'
    full_dir.mkdir(parents=True, exist_ok=True)
    full_path = full_dir / 'index.json'

    if regenerate or not full_path.exists():
        rag = RAG(
            config,
            graph_dir=str(kg_dir),
            cache_dir=str(kg_dir / '.hi_cache'),
            graphs_root=str(kg_dir.parent),
            run_id=run_id,
        )
        rag.dump_index(str(full_path))

    chunk_payload = json.loads(full_path.read_text(encoding='utf-8')).get('chunks', {})

    graph_path = kg_dir / '.hi_cache' / 'graph_chunk_entity_relation.graphml'
    if not graph_path.exists():
        raise FileNotFoundError(f'GraphML not found at {graph_path}')

    nodes, edges = extract_graph_data(graph_path)
    metadata = {
        'run_id': run_id,
        'ts': datetime.now(timezone.utc).isoformat(),
    }
    return {
        'kg_id': _kg_id_from_path(kg_dir),
        'metadata': metadata,
        'nodes': nodes,
        'edges': edges,
        'chunks': chunk_payload,
    }


def build_trimmed(data: Dict[str, Any], fraction: float) -> Dict[str, Any]:
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    chunks = data.get('chunks', {})
    if not nodes:
        return data

    keep_count = max(1, int(len(nodes) * fraction))
    keep_nodes = nodes[:keep_count]
    keep_ids: Set[str] = {node['id'] for node in keep_nodes if 'id' in node}

    keep_edges = [edge for edge in edges if edge.get('source') in keep_ids and edge.get('target') in keep_ids]

    referenced_chunks: Set[str] = set()
    for node in keep_nodes:
        for cid in node.get('source_ids', []) or []:
            referenced_chunks.add(str(cid))
    keep_chunks = {cid: chunks[cid] for cid in referenced_chunks if cid in chunks}

    trimmed = {
        'kg_id': data.get('kg_id'),
        'metadata': data.get('metadata', {}),
        'nodes': keep_nodes,
        'edges': keep_edges,
        'chunks': keep_chunks,
    }
    return trimmed


def write_index(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kg-dir', required=True, type=Path, help='Path to the KG directory (e.g. rag/kgs/cooking_kg/hi)')
    parser.add_argument('--config', default='rag/config.yaml', help='Path to rag config')
    parser.add_argument('--run-id', default='trim_index', help='Run id used when dumping the full index')
    parser.add_argument('--fraction', type=float, default=0.5, help='Fraction of nodes to keep in the trimmed index')
    parser.add_argument('--regenerate', action='store_true', help='Force regeneration of the full index before trimming')
    args = parser.parse_args()

    kg_dir = args.kg_dir.resolve()
    if not kg_dir.exists():
        raise FileNotFoundError(f'KG directory not found: {kg_dir}')

    full_data = dump_full_index(kg_dir, args.config, args.run_id, args.regenerate)
    full_path = kg_dir / 'full_index' / 'index.json'
    write_index(full_path, full_data)

    trimmed_data = build_trimmed(full_data, args.fraction)
    write_index(kg_dir / 'index.json', trimmed_data)
    print(f'Trimmed index written to {kg_dir / "index.json"}')


if __name__ == '__main__':
    main()
