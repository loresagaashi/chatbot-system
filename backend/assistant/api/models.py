from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class ChatSession(models.Model):
    """
    Represents a single chat session/conversation.

    In a more advanced setup this could be linked directly to a user account;
    for now sessions are anonymous, but long‑term memories can still be tied
    back to them.
    """

    title = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.title or f"Session {self.pk}"


class Message(models.Model):
    """
    Individual message within a chat session.
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
        help_text="Chat session this message belongs to.",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        help_text="Who sent the message: user or assistant.",
    )
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]


class ProfessionalDocument(models.Model):
    """
    A piece of professional data for a user (CV, document, notes, skills,
    experience, etc.) whose content is embedded for semantic search.

    The `embedding` is stored as a pgvector `VectorField`, which allows fast
    similarity search in PostgreSQL when used with the pgvector extension.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professional_documents",
        null=True,
        blank=True,
        help_text="Optional owner of the document; null for anonymous usage.",
    )
    title = models.CharField(max_length=255)
    content = models.TextField(
        help_text="Plain text content of the professional document (CV, notes, etc.)."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # Embedding stored as a pgvector field; populated by the embedding service.
    embedding = VectorField(
        dimensions=settings.EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
        help_text="Vector embedding of the content for semantic search.",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional extra metadata such as tags, skills, experience level.",
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.title


class MemoryEntry(models.Model):
    """
    Long‑term memory entry for the assistant.

    These are auto‑created from conversations or via APIs and embedded so that
    we can retrieve them semantically and provide personalized responses.
    """

    SOURCE_CHAT = "chat"
    SOURCE_DOCUMENT = "document"
    SOURCE_MANUAL = "manual"

    SOURCE_CHOICES = [
        (SOURCE_CHAT, "Chat"),
        (SOURCE_DOCUMENT, "Document"),
        (SOURCE_MANUAL, "Manual"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memories",
        null=True,
        blank=True,
        help_text="User this memory belongs to; null when anonymous.",
    )
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        related_name="memories",
        null=True,
        blank=True,
        help_text="Optional chat session that produced this memory.",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_CHAT,
        help_text="Where this memory came from.",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional short label for the memory.",
    )
    content = models.TextField(
        help_text="The remembered fact, summary, preference, or detail about the user."
    )
    importance = models.IntegerField(
        default=0,
        help_text=(
            "A simple integer importance score. Higher values indicate the memory "
            "is more important and should be preferred when selecting context."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft‑delete flag; inactive memories are ignored in retrieval.",
    )

    # Embedding stored as a pgvector field.
    embedding = VectorField(
        dimensions=settings.EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
        help_text="Vector embedding of the memory content for semantic search.",
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-importance", "-updated"]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return self.title or self.content[:80]
