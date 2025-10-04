"" Hey if you want to use this folder first do these pip installs,
- cd into this folder and run: `python -m pip install -r requirements.txt`
- optional: create a virtualenv first (`python -m venv .venv` then `./.venv/Scripts/activate` on Windows)
## Overview
This `rag` folder bundles everything needed to index a pile of `.txt` documents with HiRAG and reuse the cached graph/embeddings. It exposes a small Python facade plus a CLI helper.
### 1. Prepare your environment
1. Copy your OpenAI key (or other provider settings) to `.env` in the project root:
   ```env
   OPENAI_API_KEY=sk-...
   ```
2. Adjust `config.yaml` if you want to change cache locations, switch embedders (`e5` vs `openai`), or tweak HiRAG knobs. The defaults now write graphs under `kgs/<graph-name>/<mode>/.hi_cache`.
### 2. Build an index from books
1. Drop your `.txt` files into `books/` (the sample `demo.txt` lives there already).
2. Run the builder (from the repo root or from inside the folder):
   ```bash
   python -m rag.cli --book books/demo.txt
   ```
   The knowledge graph cache and index land under `kgs/sample_graph/hi/` by default, and `index.json` is regenerated unless you pass `--skip-dump`.
### 3. Use the runner in your own scripts
```python
from rag import RAG
rag = RAG()  # reads rag/config.yaml by default
rag.build_from_file("rag/books/demo.txt")  # optional if you want to ingest programmatically
context = rag.retrieve("Who is mentioned in the book?")
print(context["node_datas"])
answer = rag.answer("Who is Al-Mutanabbi?", include_context=True)
print(answer["answer"])
print(len(answer["context"]["use_text_units"]), "chunks used")  # context payload mirrors rag.retrieve() output
# You can override defaults per-call
follow_up = rag.answer("Give me a concise bullet list for classroom use", top_k=6, system_prompt="Speak in teaching bullets.")
print(follow_up["answer"])
```
You can override paths at construction time:
```python
rag = RAG(cache_dir="/tmp/kgs/cooking", logs_path="/tmp/kgs")
```
`cache_dir` can point to the graph folder (the toolkit will create `<mode>/.hi_cache` inside) or directly to an existing `.hi_cache` path. `logs_path` is the root directory that holds every graph and is where new graph folders will be created if you do not override `cache_dir` separately.
### 4. Plug into your agent loop

**Instantiate once**
- `RAG(config_path=None, cache_dir=..., logs_path=..., run_id=...)` loads `config.yaml`, resolves cache/log dirs, and creates a `HiRAGRunner`.
- Pass overrides such as `RAG(cache_dir='/tmp/kgs/research', run_id='agent-run')` to keep experiments isolated.

**Key methods**
- `retrieve(query, top_k=8)` returns the structured context dict (`use_text_units`, `use_communities`, `use_reasoning_path`, `node_datas`).
- `answer(query, top_k=8, include_context=True, system_prompt=None, model=None)` wraps the built-in chat completion. Set `include_context=True` when you want the raw evidence, or override `model/system_prompt` per call.
- `build_from_file(path)` / `build(docs)` let you ingest additional text before serving queries.

**Agent wiring snippet**
```python
rag = RAG(run_id='support-agent')
def call_agent(user_msg: str) -> str:
    ctx = rag.retrieve(user_msg, top_k=6)
    prompt = render_prompt(user_msg, ctx)  # your template function
    llm_reply = llm.chat(prompt)
    return llm_reply
```

Or lean on the built-in answer helper:
```python
rag = RAG()
reply = rag.answer(user_msg, top_k=6, system_prompt='Act as a concise helpdesk agent.')
if reply.get('context'):
    store_context(reply['context'])  # log or display evidence
return reply['answer']
```

**Tips**
- When `retrieve` returns empty lists, your agent should decide whether to ask for clarification or escalate.
- You can call `retrieve` first to show evidence in the UI, then call `answer` only if needed.
- Add additional modes under `config.yaml > modes:` and construct `RAG(mode='naive')` (once configured) to experiment with different retrieval strategies.

### CLI extras
- `python -m rag.cli --dump-only` refreshes `index.json` without inserting new documents.
- `python -m rag.cli --cache /custom/kgs/graph-name --logdir /custom/kgs --book books/my.txt` lets you redirect where graphs live.
### Housekeeping
- Delete `kgs/<graph-name>` if you want a fresh rebuild for that graph.
- The CLI auto-loads `.env` on first use, so you do not need to export the key manually each run.
- When using non-OpenAI embeddings, edit `config.yaml` (`default_embedding.class: e5`) and ensure the required model files are available locally.
See `rag_examples.py` for a comment-heavy walkthrough with additional scenarios.

