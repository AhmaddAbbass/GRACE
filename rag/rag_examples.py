"""hey user! this file is a hands-on tour of the rag toolkit.

Example 1: Use the retriever as a context provider and inspect the raw nuggets that come back.
Example 2: Compare retrieval output with different knobs (top_k, modes) so you understand how the cache behaves.
Example 3: Wrap the retriever + answer helper into a tiny chatbot loop that feeds context into an LLM.

Feel free to copy/paste the snippets into your own scripts or run the helpers in-place.
"""
from __future__ import annotations

import os
from pathlib import Path
from textwrap import indent

from rag import RAG

# --------------------------------------------------------------------------------------
# Example 1 ---------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
def example_1_basic_context(query: str = "Who is mentioned in the book?", *, top_k: int = 4) -> None:
    """Retrieve context for a single query and pretty-print the pieces."""
    rag = RAG()
    context = rag.retrieve(query, top_k=top_k)

    print("\n=== Example 1: Context provider ===")
    print(f"Query      : {query}")
    print(f"Top-k used : {top_k}")
    print("\nText units (chunk excerpts):")
    for idx, unit in enumerate(context.get("use_text_units", []), 1):
        preview = unit.get("content", "").strip()
        preview = preview[:240] + ("..." if len(preview) > 240 else "")
        print(indent(f"[{idx}] {preview}", "  "))

    if context.get("node_datas"):
        print("\nEntity mentions:")
        for node in context["node_datas"]:
            print(indent(f"- {node.get('entity_name')} ({node.get('entity_type')}) :: {node.get('description')}", "  "))

    if context.get("use_reasoning_path"):
        print("\nReasoning path hops:")
        for hop in context["use_reasoning_path"]:
            src, tgt = hop.get("src_tgt", ("", ""))
            print(indent(f"{src} -> {tgt}: {hop.get('description')}", "  "))

# --------------------------------------------------------------------------------------
# Example 2 ---------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
def example_2_compare_modes(query: str = "What does the book talk about?", *, small_top_k: int = 2, large_top_k: int = 6) -> None:
    """Show how tweaking retrieval knobs (or modes) changes the context you get back."""
    rag_default = RAG()
    print("\n=== Example 2: Comparing retrieval knobs ===")
    ctx_small = rag_default.retrieve(query, top_k=small_top_k)
    ctx_large = rag_default.retrieve(query, top_k=large_top_k)

    def describe(label: str, ctx: dict[str, list[dict[str, str]]], top_k: int) -> None:
        print(f"\n-- {label} (top_k={top_k})")
        print(f"Chunks: {len(ctx.get('use_text_units', []))}, Entities: {len(ctx.get('node_datas', []))}")
        for unit in ctx.get("use_text_units", [])[:2]:
            preview = unit.get("content", "").strip()
            preview = preview[:200] + ("..." if len(preview) > 200 else "")
            print(indent(preview, "    "))

    describe("Default settings", ctx_small, small_top_k)
    describe("More context", ctx_large, large_top_k)

    print("\nTip: if you add more modes to config.yaml (e.g. 'naive', 'graph'), instantiate RAG(mode='naive') to compare behaviour across runners.")

# --------------------------------------------------------------------------------------
# Example 3 ---------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
def example_3_chat_loop(prompt: str = "You are a study buddy that answers with the provided context.") -> None:
    """Minimal chatbot shell that keeps querying until the user types 'exit'."""
    rag = RAG()
    print("\n=== Example 3: Chatbot loop ===")
    print("Type 'exit' to stop. Each turn runs rag.answer(), which pipes context into OpenAI chat completions and falls back only when no supporting context is retrieved.")
    while True:
        question = input("user> ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit", "bye"}:
            print("assistant> Goodbye!")
            break
        response = rag.answer(question, include_context=False, system_prompt=prompt)
        print("assistant>", response.get("answer", ""))

# --------------------------------------------------------------------------------------
# Bonus ideas -------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
BONUS_NOTES = """
More ideas you can explore:
  * Build a batch evaluator: feed a list of questions and dump the contexts to JSON for later analysis.
  * Plug the retriever into an agent / tool-calling loop and let the LLM decide when to refresh context.
  * Swap embeddings in config.yaml (e5 vs openai) and measure retrieval differences with Example 2.
  * Use rag.answer(..., include_context=True) and pass the context downstream to grading or UI layers.
"""


def print_bonus_notes() -> None:
    print("\n=== Bonus ideas ===")
    print(BONUS_NOTES)


if __name__ == "__main__":
    # toggle the examples you want to run. Example 1 prints context; Example 2 runs two retrievals;
    # Example 3 enters an interactive loop (comment it out if you do not want to chat right now).
    example_1_basic_context()
    example_2_compare_modes()
    example_3_chat_loop()  # uncomment to launch the interactive chatbot
    print_bonus_notes()
