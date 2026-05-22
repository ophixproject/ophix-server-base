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

    _orig_get       = _mgmt.get_commands
    _orig_fetch     = _mgmt.ManagementUtility.fetch_command
    _orig_help_text = _mgmt.ManagementUtility.main_help_text

    def _filtered_fetch(self, subcommand):
        if subcommand in _HIDDEN_COMMANDS:
            self.stderr.write(
                "Unknown command: %r\nType '%s help' for usage.\n"
                % (subcommand, self.prog_name)
            )
            sys.exit(1)
        return _orig_fetch(self, subcommand)

    def _filtered_help_text(self, commands_only=False):
        # Temporarily narrow get_commands so hidden entries don't appear in --help.
        _mgmt.get_commands = lambda: {
            k: v for k, v in _orig_get().items() if k not in _HIDDEN_COMMANDS
        }
        try:
            return _orig_help_text(self, commands_only=commands_only)
        finally:
            _mgmt.get_commands = _orig_get

    _mgmt.ManagementUtility.fetch_command   = _filtered_fetch
    _mgmt.ManagementUtility.main_help_text  = _filtered_help_text


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
