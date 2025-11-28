"""URL configuration for surrealdb_example project."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


async def health(request):
    """Health check endpoint."""
    return JsonResponse({"status": "ok", "database": "connected"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/", include("api.urls")),
]
