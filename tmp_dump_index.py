from pathlib import Path
from rag import RAG
rag = RAG('rag/config.yaml', graph_dir='rag/kgs/cooking_kg/hi', cache_dir='rag/kgs/cooking_kg/hi/.hi_cache', graphs_root='rag/kgs', run_id='cooking_kg')
output = Path('rag/kgs/cooking_kg/hi/index.json')
rag.dump_index(str(output))
print(f"Wrote {output.resolve()}")
