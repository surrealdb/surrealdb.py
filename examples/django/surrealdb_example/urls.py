"""URL configuration for surrealdb_example project."""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


async def health(request):
    """Health check endpoint."""
    return JsonResponse({"status": "ok", "database": "connected"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/", include("api.urls")),
]
