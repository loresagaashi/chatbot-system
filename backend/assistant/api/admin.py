from django.contrib import admin
import json

from .models import Message, ProfessionalDocument, MemoryEntry


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "short_text", "created")
    search_fields = ("text", "session__id")
    list_filter = ("role", "session")
    readonly_fields = ("created",)

    def short_text(self, obj):
        text = obj.text or ""
        return (text[:75] + "...") if len(text) > 75 else text

    short_text.short_description = "Text"


@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(admin.ModelAdmin):
    """
    Admin view for professional documents (e.g. CV, notes).

    Shows the original text content and a pretty‑printed view of the stored
    embedding vector so you can inspect how the document is represented in the
    vector database.
    """

    list_display = ("id", "title", "owner", "created", "updated")
    search_fields = ("title", "content", "owner__username")
    readonly_fields = ("created", "updated", "formatted_embedding")

    fieldsets = (
        (
            "Metadata",
            {
                "fields": ("owner", "title", "metadata", "created", "updated"),
            },
        ),
        (
            "Content",
            {
                "fields": ("content",),
            },
        ),
        (
            "Embedding",
            {
                "fields": ("formatted_embedding",),
                "description": "Vector embedding as stored in the database (pgvector).",
            },
        ),
    )

    def formatted_embedding(self, obj):
        """
        Return a readable JSON representation of the embedding vector.

        We normalise pgvector / numpy types to plain Python floats so that
        json.dumps can serialize them without errors.
        """
        if obj.embedding is None:
            return "(no embedding)"

        try:
            raw = list(obj.embedding)
        except TypeError:
            raw = obj.embedding

        # Convert each element to a built-in float (handles numpy.float32, etc.)
        try:
            data = [float(x) for x in raw]
        except TypeError:
            data = raw

        return json.dumps(data, indent=2)[:4000]  # avoid rendering extremely long text

    formatted_embedding.short_description = "Embedding vector"


@admin.register(MemoryEntry)
class MemoryEntryAdmin(admin.ModelAdmin):
    """
    Admin view for long‑term memory entries.

    Displays the remembered content alongside its embedding so you can verify
    what the assistant has stored as long‑term memory.
    """

    list_display = ("id", "owner", "session", "source", "importance", "is_active")
    list_filter = ("source", "is_active", "importance")
    search_fields = ("content", "title", "owner__username")
    readonly_fields = ("created", "updated", "formatted_embedding")

    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "owner",
                    "session",
                    "source",
                    "title",
                    "importance",
                    "is_active",
                    "created",
                    "updated",
                ),
            },
        ),
        (
            "Content",
            {
                "fields": ("content",),
            },
        ),
        (
            "Embedding",
            {
                "fields": ("formatted_embedding",),
                "description": "Vector embedding corresponding to the memory content.",
            },
        ),
    )

    def formatted_embedding(self, obj):
        if obj.embedding is None:
            return "(no embedding)"

        try:
            raw = list(obj.embedding)
        except TypeError:
            raw = obj.embedding

        try:
            data = [float(x) for x in raw]
        except TypeError:
            data = raw

        return json.dumps(data, indent=2)[:4000]

    formatted_embedding.short_description = "Embedding vector"