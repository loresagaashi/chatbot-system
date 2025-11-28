from rest_framework import routers
from .views import ChatSessionViewSet, MessageViewSet, chat
from django.urls import path, include

router = routers.DefaultRouter()
router.register('sessions', ChatSessionViewSet, basename='chatsession')
router.register('messages', MessageViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('chat/', chat),
]
