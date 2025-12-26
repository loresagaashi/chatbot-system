from django.conf import settings
from openai import OpenAI
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .embedding_utils import embed_text
from .memory import (
    build_retrieval_context,
    create_memory_from_message,
    ensure_document_embedding,
)
from .models import ChatSession, MemoryEntry, Message, ProfessionalDocument
from .serializers import (
    ChatSessionSerializer,
    MemoryEntrySerializer,
    MessageSerializer,
    ProfessionalDocumentSerializer,
)
import os


def _get_openai_client() -> OpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")
    return OpenAI(api_key=api_key)


def _call_openai_for_text(
    user_message: str,
    *,
    system_context: str | None = None,
    history: list[dict] | None = None,
) -> str:
    """
    Helper that calls OpenAI with the given user message and returns the text.

    `system_context` is injected as a system‑role message and typically
    contains retrieved memories and professional documents. `history` is an
    optional list of prior chat messages (as dicts with `role` and `content`).
    """
    client = _get_openai_client()

    messages: list[dict] = []

    if system_context:
        messages.append({"role": "system", "content": system_context})

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_message})

    completion = client.chat.completions.create(
        model=getattr(settings, "CHAT_MODEL_NAME", "gpt-4o-mini"),
        messages=messages,
    )
    return completion.choices[0].message.content

class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for chat sessions.
    """

    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        """
        Return chat sessions.

        Historically this view only returned sessions that had at least one
        message so that automatically created but unused chats would not
        clutter history. Now that the UI allows the user to explicitly create
        a new (empty) chat from the sidebar, we return all sessions so that
        user‑created empty chats are also visible in the history.
        """
        qs = super().get_queryset()
        return qs.distinct()


class MessageViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for Message model.
    """

    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def get_queryset(self):
        """
        Optionally filter messages by chat session id using ?session=<id>.
        """
        qs = super().get_queryset()
        session_id = self.request.query_params.get("session")
        if session_id:
            qs = qs.filter(session_id=session_id)
        return qs

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        """
        Regenerate an assistant reply for a specific *user* message.
        Creates a new assistant Message row and returns it.
        """
        message = self.get_object()
        if message.role != Message.ROLE_USER:
            return Response(
                {"error": "Can only regenerate for user messages."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        text = (message.text or "").strip()
        if not text:
            return Response(
                {"error": "Message text is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Message.objects.filter(session=message.session, id__gt=message.id).delete()

        # Build conversation history up to (but excluding) this message so the
        # assistant can respond in context.
        history_messages: list[dict] = []
        if message.session_id:
            prior_messages = Message.objects.filter(
                session_id=message.session_id, id__lt=message.id
            ).order_by("created")
            for m in prior_messages:
                role = "user" if m.role == Message.ROLE_USER else "assistant"
                history_messages.append({"role": role, "content": m.text})

        request_user = request.user if getattr(request, "user", None) else None

        # Compute an embedding for the edited user message and retrieve
        # relevant long‑term memories and documents to use as a system prompt.
        try:
            query_embedding = embed_text(text)
            system_context = build_retrieval_context(
                user=request_user, query_text=text, query_embedding=query_embedding
            )

            ai_answer = _call_openai_for_text(
                text,
                system_context=system_context,
                history=history_messages,
            )

            # Store this (edited) message as a new memory as well so that
            # future turns can benefit from it.
            create_memory_from_message(
                user=request_user,
                session=message.session,
                text=text,
                embedding=query_embedding,
            )
        except RuntimeError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to get response from OpenAI: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        assistant_message = Message.objects.create(
            session=message.session,
            role=Message.ROLE_ASSISTANT,
            text=ai_answer,
        )
        return Response(MessageSerializer(assistant_message).data)


class ProfessionalDocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for professional documents (CVs, notes, skills, etc.).

    On create/update the backend automatically generates or refreshes the
    embedding so that documents immediately participate in semantic search.
    """

    queryset = ProfessionalDocument.objects.all()
    serializer_class = ProfessionalDocumentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            qs = qs.filter(owner=user)
        return qs

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        instance = serializer.save(
            owner=user if user and getattr(user, "is_authenticated", False) else None
        )
        ensure_document_embedding(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        ensure_document_embedding(instance)


class MemoryEntryViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for long‑term memories.

    While most memories are created automatically from chat messages, this
    endpoint allows manual inspection and curation when desired.
    """

    queryset = MemoryEntry.objects.all()
    serializer_class = MemoryEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            qs = qs.filter(owner=user)
        return qs

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        instance = serializer.save(
            owner=user if user and getattr(user, "is_authenticated", False) else None
        )
        # Ensure a fresh embedding for the created memory.
        instance.embedding = embed_text(instance.content or "")
        instance.save(update_fields=["embedding", "updated"])

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.embedding = embed_text(instance.content or "")
        instance.save(update_fields=["embedding", "updated"])


@api_view(["POST"])
def chat(request):
    """
    Simple chat endpoint that accepts a user message and forwards it to
    OpenAI if an API key is configured.

    Request JSON body:
    {
      "message": "Hello"
    }

    Response JSON body:
    {
      "response": "... AI answer ..."
    }
    """
    user_message = request.data.get("message", "").strip()
    if not user_message:
        return Response(
            {"error": "Missing 'message' in request body."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    session_id = request.data.get("session")
    session = None
    if session_id is not None:
        try:
            session = ChatSession.objects.get(pk=session_id)
        except ChatSession.DoesNotExist:
            return Response(
                {"error": "Invalid chat session id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    request_user = request.user if getattr(request, "user", None) else None

    # Build history of prior messages in this session so the assistant can
    # respond with full conversational context.
    history_messages: list[dict] = []
    if session:
        prior_messages = Message.objects.filter(session=session).order_by("created")
        for m in prior_messages:
            role = "user" if m.role == Message.ROLE_USER else "assistant"
            history_messages.append({"role": role, "content": m.text})

    try:
        # Embed the new user message once so we can both search and create
        # memory entries without duplicating work.
        query_embedding = embed_text(user_message)

        system_context = build_retrieval_context(
            user=request_user,
            query_text=user_message,
            query_embedding=query_embedding,
        )

        ai_answer = _call_openai_for_text(
            user_message,
            system_context=system_context,
            history=history_messages,
        )

        # Persist a new long‑term memory derived from this message.
        create_memory_from_message(
            user=request_user,
            session=session,
            text=user_message,
            embedding=query_embedding,
        )
    except RuntimeError as e:
        return Response(
            {"error": f"OpenAI API key is not configured on the server: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        return Response(
            {"error": f"Failed to get response from OpenAI: {e}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    Message.objects.create(session=session, role=Message.ROLE_USER, text=user_message)
    Message.objects.create(
        session=session, role=Message.ROLE_ASSISTANT, text=ai_answer
    )

    return Response({"response": ai_answer})
