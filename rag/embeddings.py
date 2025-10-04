# rag/embeddings.py
# tiny, optional embedders so HiRAG has something to call.
# if you already have your own object, pass it via RAG(..., embedding_func=my_embedder)

from typing import List, Any, Sequence

# Try sentence-transformers for a local model
try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:
    _HAS_ST = False

# Try OpenAI (>=1.0)
try:
    import openai
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False


class E5Embedding:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-base"):
        if not _HAS_ST:
            raise RuntimeError("sentence_transformers not installed for E5Embedding")
        self.model = SentenceTransformer(model_name)
        try:
            dim = int(self.model.get_sentence_embedding_dimension())
        except Exception:
            try:
                dim = len(self.model.encode(["dimension probe"])[0])
            except Exception:
                dim = 0
        self.embedding_dim = dim or 768

    # common HiRAG embedder interface patterns
    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()

    def embed(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    async def __call__(self, texts: Sequence[str] | str):
        batch = [texts] if isinstance(texts, str) else list(texts)
        return self.embed_documents(batch)


class OpenAIEmbedding:
    def __init__(self, model: str = "text-embedding-3-small"):
        if not _HAS_OPENAI:
            raise RuntimeError("openai package not installed")
        self.model = model
        # expects OPENAI_API_KEY in env
        self.embedding_dim = _guess_openai_dim(model)

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        # minimal, synchronous embedder
        client = openai.OpenAI()
        out = client.embeddings.create(model=self.model, input=list(texts))
        return [d.embedding for d in out.data]

    def embed(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    async def __call__(self, texts: Sequence[str] | str):
        batch = [texts] if isinstance(texts, str) else list(texts)
        return self.embed_documents(batch)


class _ZeroEmb:
    embedding_dim = 16

    def embed_documents(self, texts: Sequence[str]):
        return [[0.0] * self.embedding_dim for _ in texts]

    def embed(self, text: str):
        return [0.0] * self.embedding_dim

    async def __call__(self, texts: Sequence[str] | str):
        batch = [texts] if isinstance(texts, str) else list(texts)
        return self.embed_documents(batch)


def make_default_embedding(cfg) -> Any:
    """
    cfg like:
      {class: "e5"} or {class: "openai", model: "..."}
    """
    cls = (cfg or {}).get("class", "e5").lower()
    if cls in ("e5", "e5base", "e5-base"):
        return E5Embedding(cfg.get("model", "intfloat/multilingual-e5-base"))
    if cls in ("openai", "oai"):
        return OpenAIEmbedding(cfg.get("model", "text-embedding-3-small"))
    return _ZeroEmb()


def _guess_openai_dim(model_name: str) -> int:
    table = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    return table.get(model_name, 1536)
