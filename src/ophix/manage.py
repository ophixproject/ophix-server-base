#!/usr/bin/env python
"""
Django management entry point for Ophix Project Servers.

Usage::

    python -m ophix.manage <command> [options]

Or via the console_scripts entry point installed by ophix-server-base::

    ophix-manage <command> [options]
"""

import sys
import os
from pathlib import Path


def _chdir_to_server_root():
    """Change to the server root so find_dotenv(usecwd=True) finds .env.

    When ophix-manage is invoked from an arbitrary directory the dotenv
    search misses the .env that lives alongside the venv.  The venv is
    always a direct child of the server root, so sys.executable is always
    at <server_root>/<venv>/bin/python — three levels up is the server root.
    Only chdir when a .env actually exists there; leaves dev environments
    (where the layout differs) untouched.
    """
    server_root = Path(sys.executable).resolve().parent.parent.parent
    if (server_root / ".env").exists():
        os.chdir(server_root)


def main():
    _chdir_to_server_root()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ophix.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. Are you sure it is installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
