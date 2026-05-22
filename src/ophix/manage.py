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
    search misses the .env that lives alongside the venv.  sys.prefix is
    always the venv directory itself (no symlink ambiguity), so its parent
    is reliably the server root.  Only chdir when a .env actually exists
    there; leaves dev environments (where the layout differs) untouched.
    """
    server_root = Path(sys.prefix).parent
    if (server_root / ".env").exists():
        os.chdir(server_root)


_HIDDEN_COMMANDS = frozenset([
    # Schema development tools — not for production servers
    "makemigrations",
    "squashmigrations",
    "showmigrations",
    "sqlmigrate",
    "sqlflush",
    "inspectdb",
    # Interactive shells — security risk on production
    "shell",
    "dbshell",
    "diffsettings",
    # Destructive
    "flush",
    # Development servers — replaced by gunicorn/nginx
    "runserver",
    "testserver",
    # Test runner — not needed on a deployed server
    "test",
    # Project scaffolding — irrelevant post-install
    "startapp",
    "startproject",
    # Translation compilation — dev workflow only
    "compilemessages",
])


def _patch_hidden_commands():
    from django.core import management as _mgmt
    _orig = _mgmt.get_commands

    def _filtered():
        return {k: v for k, v in _orig().items() if k not in _HIDDEN_COMMANDS}

    _mgmt.get_commands = _filtered


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
    _patch_hidden_commands()
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
