# Project: Graphs of Algorithms — a Traversal-First Assistant

We’re building a multi-domain platform that organizes **algorithms as knowledge graphs** and uses those graphs to answer questions, explain solutions, and even **compose new algorithms**. Each domain—e.g., **cooking**, **computer science**, **IKEA assembly**—gets its own graph. In a graph, **nodes** represent meaningful units (steps, functions, tools, variables, resources) and **edges** capture relations (calls, depends-on, transforms, produces, precondition-of, part-of). An individual algorithm appears as a **path/subgraph** (e.g., *boil → cool → peel* for eggs; or *partition → recurse → merge* for sorting). Critically, graphs also encode **cross-algorithm links**, so ideas from Algorithm A, B, and C can be stitched or contrasted when solving something new.

At query time, an **orchestrator agent** routes your question to the most relevant graph(s) and retrieves **both local subgraphs** (entity-centric neighborhoods, multi-hop paths) and **global structure** (communities/themes). That graph context is packaged—along with optional **web search results**—for the LLM, which produces a solution/plan and **cites** its provenance directly to graph nodes and original text snippets. The result isn’t just an answer; it’s an answer with a visible **“why” path** you can inspect, learn from, and reuse.

Under the hood, our ingestion pipeline converts text sources (docs, recipes, code, manuals) into graph structure. We extract steps/functions, identify inputs/outputs and pre/postconditions, and add edges like *calls*, *uses*, *requires*, *produces*. We also connect **similar motifs across algorithms** (e.g., “priority-queue selection” in Dijkstra ↔ “task scheduling” in cooking mise en place) so the system can reuse ideas. Over time, these graphs become a living library of **algorithmic motifs** that can be recombined: sometimes to propose a **new composition** (“Algorithm C”) and sometimes to explain **trade-offs** between alternatives.

The **UI** is split-view. On the **left**, a chat with the agent (ask “How do I cook a jammy egg?” or “Design a stable, O(n log n) sort for nearly-sorted arrays”). On the **right**, an interactive **graph visualization** that shows what the assistant used: highlighted nodes/edges, the subgraph it traversed, and links back to source snippets. You can click any node to read the exact chunk it came from, expand neighborhoods, or pin alternatives. This makes the system **explainable** (clear provenance), **educational** (see the structure of solutions), and **extensible** (you can edit or add nodes).

What this enables:

* **Graph-aware retrieval**: multi-hop reasoning, community summaries, and entity-centric neighborhoods—richer than naive chunk search.
* **Composition & transfer**: reuse steps from different algorithms to draft a new plan, with constraints (types/preconditions) checked.
* **Provenance by design**: every claim maps to nodes/edges and the source texts; answers cite A/B/C so users can verify and learn.
* **Cross-domain utility**: the same pattern works for cooking, CS algorithms, and assembly instructions—anywhere procedures and relations matter.

**Examples.**
*Cooking*: “Jammy egg in 8 minutes?” → retrieves subgraph (boil→rest→cool→peel), shows timing nodes and safety notes; optionally suggests variants (steam vs boil).
*CS*: “Fast edit distance for near-matches” → pulls DP subgraph and suggests banded DP; cites where *banding* appears in string-matching literature; shows complexity nodes.
*IKEA*: “Assemble LACK table” → step graph with *requires tool*, *depends-on*, *safety* edges; highlights common subroutines reused from other furniture.

**Stretch capabilities (planned):** typed contracts on nodes (inputs/outputs, pre/postconditions), lightweight checking so compositions are valid; rewrite rules to explore equivalent subgraphs (choose best by a cost model); property-based tests on synthesized plans; agentic web-search augmentation with strict citation.

---

### Drop-in prompt you can reuse

Use this as your system/instruction block when chatting with the model:

```
You are an assistant that answers user queries by leveraging:
1) a knowledge graph of algorithms (nodes: steps/functions/tools/variables with types and pre/postconditions; edges: calls/depends-on/produces/part-of/precondition-of),
2) retrieved subgraphs and community summaries ("context"),
3) optional web search results.

Task: Given the user's query {query}, use the provided {context} (graph nodes/edges + source snippets) and {search_results} to produce a clear solution or algorithmic plan. 
- Explain the reasoning with references to specific graph nodes/edges.
- Cite sources (graph nodes with their original text snippets, and web sources if used).
- Prefer stepwise, verifiable instructions and mention assumptions/preconditions.
- If multiple valid approaches exist, compare them and state trade-offs.
```

