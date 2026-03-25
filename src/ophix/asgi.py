"""
ophix.asgi
~~~~~~~~~~
ASGI entry point for all Ophix Project Servers.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ophix.settings")
application = get_asgi_application()
