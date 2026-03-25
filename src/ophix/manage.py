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


def main():
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
