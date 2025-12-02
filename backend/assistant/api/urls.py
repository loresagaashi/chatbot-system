from django.urls import include, path
from rest_framework import routers

from .views import (
    ChatSessionViewSet,
    MemoryEntryViewSet,
    MessageViewSet,
    ProfessionalDocumentViewSet,
    chat,
)

router = routers.DefaultRouter()
router.register("sessions", ChatSessionViewSet, basename="chatsession")
router.register("messages", MessageViewSet)
router.register("documents", ProfessionalDocumentViewSet, basename="document")
router.register("memories", MemoryEntryViewSet, basename="memory")

urlpatterns = [
    path("", include(router.urls)),
    path("chat/", chat),
]
