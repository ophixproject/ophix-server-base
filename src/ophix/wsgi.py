"""
ophix.wsgi
~~~~~~~~~~
WSGI entry point for all Ophix Project Servers.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ophix.settings")
application = get_wsgi_application()
