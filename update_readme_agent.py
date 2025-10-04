from pathlib import Path

path = Path('rag/README.md')
text = path.read_text(encoding='utf-8')
insertion = "### 4. Plug into your agent loop\n\n**Instantiate once**\n- `RAG(config_path=None, cache_dir=..., logs_path=..., run_id=...)` loads `config.yaml`, resolves cache/log dirs, and creates a `HiRAGRunner`.\n- Any argument you pass overrides the YAML (e.g. `RAG(cache_dir='/tmp/hirag', run_id='agent-run')`).\n\n**Key methods**\n- `retrieve(query, top_k=8)` ? returns the structured context dict (`use_text_units`, `use_communities`, `use_reasoning_path`, `node_datas`). Perfect for stuffing into your own prompt templates or memory stores.\n- `answer(query, top_k=8, include_context=True, system_prompt=None, model=None)` ? uses the built-in ChatGPT-style completion. `include_context=True` echoes the same dict you’d get from `retrieve`. Override `model` or `system_prompt` per call to shape tone/length.\n- `build_from_file(path)` / `build(docs)` ? ingest new documents on the fly before serving requests.\n\n**Agent wiring snippet**\n```python
rag = RAG(run_id='support-agent')
def call_agent(user_msg: str) -> str:
    ctx = rag.retrieve(user_msg, top_k=6)
    prompt = render_prompt(user_msg, ctx)  # your template function
    llm_reply = llm.chat(prompt)
    return llm_reply
```

To let the toolkit handle prompting for you:
```python
rag = RAG()
reply = rag.answer(user_msg, top_k=6, system_prompt='Act as a concise helpdesk agent.')
if reply.get('context'):
    store_context(reply['context'])  # optional: log or display the evidence
return reply['answer']
```

**Gotchas / tips**
- Retrieval returns empty lists when the cache has no matching chunks—check `ctx['use_text_units']` before trusting downstream logic.
- For streaming agents, you can call `retrieve` first, show the snippets, then decide whether to escalate to the heavier `answer` call.
- Switch modes (e.g. naive graph vs. hierarchical) by editing `config.yaml` and constructing `RAG(mode='naive')` if you add entries under `modes:`.

"
marker = "### CLI extras"
if marker not in text:
    raise SystemExit('marker not found')
updated = text.replace(marker, insertion + "\n" + marker)
path.write_text(updated, encoding='utf-8')
