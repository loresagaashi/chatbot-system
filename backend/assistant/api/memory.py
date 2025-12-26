import math
from typing import Iterable, List, Optional, Sequence, Tuple

from django.contrib.auth import get_user_model

from .embedding_utils import embed_text
from .models import ChatSession, MemoryEntry, ProfessionalDocument

User = get_user_model()


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """
    Compute cosine similarity between two equal‑length vectors.
    Returns 0.0 if either vector has zero length.

    Note: `vec_a` / `vec_b` may be plain lists or numpy arrays (from pgvector).
    We must not rely on their truthiness (e.g. `if not vec_a`) because that is
    ambiguous for numpy arrays.
    """
    if vec_a is None or vec_b is None:
        return 0.0

    try:
        len_a = len(vec_a)
        len_b = len(vec_b)
    except TypeError:
        return 0.0

    if len_a == 0 or len_b == 0 or len_a != len_b:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def create_memory_from_message(
    *,
    user: Optional[User],
    session: Optional[ChatSession],
    text: str,
    embedding: Optional[Sequence[float]] = None,
    importance: int = 0,
) -> MemoryEntry:
    """
    Persist a new long‑term memory entry derived from a chat message.

    If no embedding is given we compute one here so that subsequent semantic
    searches can immediately pick it up.
    """
    embedding_list: Optional[List[float]]
    if embedding is None:
        embedding_list = embed_text(text)
    else:
        embedding_list = list(embedding)

    return MemoryEntry.objects.create(
        owner=user if user and getattr(user, "is_authenticated", False) else None,
        session=session,
        source=MemoryEntry.SOURCE_CHAT,
        title="",
        content=text,
        importance=importance,
        embedding=embedding_list,
    )


def ensure_document_embedding(document: ProfessionalDocument) -> ProfessionalDocument:
    """
    Ensure that the given `ProfessionalDocument` instance has an up‑to‑date
    embedding based on its content.
    """
    document.embedding = embed_text(document.content or "")
    document.save(update_fields=["embedding", "updated"])
    return document


def _iter_retrieval_candidates(
    *, user: Optional[User]
) -> Iterable[Tuple[str, float, object]]:
    """
    Internal helper to yield (kind, importance, object) tuples for all
    retrievable items for a given user.
    """
    memory_qs = MemoryEntry.objects.filter(is_active=True)
    doc_qs = ProfessionalDocument.objects.all()

    if user and getattr(user, "is_authenticated", False):
        memory_qs = memory_qs.filter(owner=user)
        doc_qs = doc_qs.filter(owner=user)

    for m in memory_qs.exclude(embedding__isnull=True):
        yield ("memory", float(m.importance or 0), m)

    for d in doc_qs.exclude(embedding__isnull=True):
        # Documents do not yet have an explicit importance field; treat them as
        # medium importance (0) for now.
        yield ("document", 0.0, d)


def build_retrieval_context(
    *,
    user: Optional[User],
    query_text: str,
    query_embedding: Optional[Sequence[float]] = None,
    top_k: int = 5,
) -> str:
    """
    Given the current user message and (optionally) its embedding, perform a
    semantic search over memories and professional documents and build a text
    block that can be injected as a system prompt for the LLM.
    """
    # Compute an embedding for the query if we were not provided one.
    if query_embedding is None:
        query_vec = embed_text(query_text or "")
    else:
        # Ensure we have a plain sequence (e.g. convert numpy arrays to list)
        query_vec = list(query_embedding)

    if len(query_vec) == 0:
        return ""

    scored_items: List[Tuple[float, str, object]] = []

    for kind, importance, obj in _iter_retrieval_candidates(user=user):
        obj_vec = getattr(obj, "embedding", None)
        if obj_vec is None:
            continue

        # Convert potential numpy arrays to plain lists for consistency
        obj_vec = list(obj_vec)

        similarity = _cosine_similarity(query_vec, obj_vec)
        if similarity <= 0.0:
            continue

        # Boost by importance so that explicitly marked memories win over
        # incidental ones.
        score = similarity + (importance * 0.01)
        scored_items.append((score, kind, obj))

    scored_items.sort(key=lambda tup: tup[0], reverse=True)
    top_items = scored_items[:top_k]

    if not top_items:
        return ""

    lines: List[str] = [
        "You have access to the following long‑term memories and user documents.",
        "Use them to personalize your response and keep details consistent over time.",
        "",
    ]

    for score, kind, obj in top_items:
        if kind == "memory":
            lines.append(f"[Memory, score={score:.3f}] {obj.content}")
        else:
            # ProfessionalDocument
            title = getattr(obj, "title", "") or "Untitled document"
            lines.append(f"[Document: {title}, score={score:.3f}] {obj.content}")

    return "\n".join(lines)


