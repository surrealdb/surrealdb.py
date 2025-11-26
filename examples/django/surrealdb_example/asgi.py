"""ASGI config for surrealdb_example project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "surrealdb_example.settings")

application = get_asgi_application()
