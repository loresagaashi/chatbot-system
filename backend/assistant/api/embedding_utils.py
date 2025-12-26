import os
from typing import Iterable, List

from django.conf import settings
from openai import OpenAI


# We read the embedding model name and dimensionality from settings so it can
# be overridden via environment variables if needed.
EMBEDDING_MODEL_NAME: str = getattr(
    settings, "EMBEDDING_MODEL_NAME", "text-embedding-3-small"
)
EMBEDDING_DIMENSIONS: int = int(
    getattr(settings, "EMBEDDING_DIMENSIONS", 1536)
)


def _get_openai_client() -> OpenAI:
    """
    Shared helper for creating an OpenAI client, respecting both Django
    settings and raw environment variables.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")
    return OpenAI(api_key=api_key)


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    """
    Generate embeddings for an iterable of strings.

    Returns a list of float vectors, ordered to match the input.
    """
    texts_list = [t or "" for t in texts]
    if not texts_list:
        return []

    client = _get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL_NAME,
        input=texts_list,
    )

    # Each data[i].embedding is already a list[float].
    return [item.embedding for item in response.data]


def embed_text(text: str) -> List[float]:
    """
    Convenience wrapper for embedding a single string.
    """
    vectors = embed_texts([text])
    return vectors[0] if vectors else []


