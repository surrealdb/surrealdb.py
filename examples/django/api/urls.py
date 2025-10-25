"""API URL configuration."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, signup, signin, logout

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/signup/', signup, name='signup'),
    path('auth/signin/', signin, name='signin'),
    path('auth/logout/', logout, name='logout'),
]

