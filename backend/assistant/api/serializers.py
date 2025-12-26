from rest_framework import serializers

from .models import ChatSession, Message, MemoryEntry, ProfessionalDocument


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["id", "title", "created"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = "__all__"


class ProfessionalDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for professional documents (CVs, notes, skills, etc.).

    The `embedding` field is read‑only; it is managed by the backend whenever
    content changes so that clients do not have to generate vectors themselves.
    """

    class Meta:
        model = ProfessionalDocument
        read_only_fields = ["embedding", "created", "updated", "owner"]
        fields = [
            "id",
            "title",
            "content",
            "metadata",
            "embedding",
            "created",
            "updated",
            "owner",
        ]


class MemoryEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for long‑term memory entries.

    The `embedding` field is read‑only for the API; the backend will create or
    refresh embeddings when memories are created or updated.
    """

    class Meta:
        model = MemoryEntry
        read_only_fields = ["embedding", "created", "updated", "owner"]
        fields = [
            "id",
            "title",
            "content",
            "importance",
            "is_active",
            "source",
            "session",
            "embedding",
            "created",
            "updated",
            "owner",
        ]
