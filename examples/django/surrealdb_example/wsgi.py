"""WSGI config for surrealdb_example project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "surrealdb_example.settings")

application = get_wsgi_application()
