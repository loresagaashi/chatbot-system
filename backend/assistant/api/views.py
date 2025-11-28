from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.conf import settings
from .models import ChatSession, Message
from .serializers import ChatSessionSerializer, MessageSerializer
from openai import OpenAI
import os


def _call_openai_for_text(user_message: str) -> str:
    """
    Helper that calls OpenAI with the given user message and returns the text.
    Raises on error so the caller can handle it.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_message}],
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
        Only return sessions that have at least one message so that
        automatically created but unused chats don't clutter history.
        """
        qs = super().get_queryset()
        return qs.filter(messages__isnull=False).distinct()


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

        try:
            ai_answer = _call_openai_for_text(text)
        except RuntimeError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"error": "Failed to get response from OpenAI."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        assistant_message = Message.objects.create(
            session=message.session,
            role=Message.ROLE_ASSISTANT,
            text=ai_answer,
        )
        return Response(MessageSerializer(assistant_message).data)


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

    try:
        ai_answer = _call_openai_for_text(user_message)
    except RuntimeError:
        return Response(
            {"error": "OpenAI API key is not configured on the server."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        return Response(
            {"error": "Failed to get response from OpenAI."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    Message.objects.create(session=session, role=Message.ROLE_USER, text=user_message)
    Message.objects.create(
        session=session, role=Message.ROLE_ASSISTANT, text=ai_answer
    )

    return Response({"response": ai_answer})
