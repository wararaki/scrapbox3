from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SnippetViewSet, UserViewSet


router = DefaultRouter()
router.register(r'snippets', SnippetViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
