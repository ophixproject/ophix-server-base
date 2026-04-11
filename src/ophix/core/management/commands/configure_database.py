"""
ophix.core.management.commands.configure_database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interactively configure the MariaDB connection and write credentials to .env.

Prompts for each database setting, showing the current value as the default.
Tests the connection directly (bypassing Django's ORM) before writing anything,
so this command is safe to run before the database schema exists.

Usage::

    ophix-manage configure_database
"""

import getpass
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from dotenv import find_dotenv, set_key


class Command(BaseCommand):
    help = (
        "Interactively configure and test the MariaDB connection, "
        "writing credentials to .env on success"
    )

    def handle(self, *args, **options):
        self.stdout.write("\nConfigure database connection\n")
        self.stdout.write("=" * 40 + "\n")
        self.stdout.write("Press Enter to keep the current value shown in [brackets].\n\n")

        # Current values from environment (set by dotenv at Django startup)
        current = {
            "DB_HOST": os.getenv("DB_HOST", "localhost"),
            "DB_PORT": os.getenv("DB_PORT", "3306"),
            "DB_NAME": os.getenv("DB_NAME", "ophix_db"),
            "DB_USER": os.getenv("DB_USER", "ophixuser"),
            "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
        }

        host, port, name, user, password = self._prompt_credentials(current)

        # Test → retry loop
        while True:
            self.stdout.write("\nTesting connection... ")
            self.stdout.flush()
            error = self._test_connection(host, port, name, user, password)
            if error is None:
                self.stdout.write(self.style.SUCCESS("OK\n"))
                break

            self.stdout.write(self.style.ERROR("FAILED\n"))
            self.stderr.write(f"  {error}\n\n")
            retry = input("Retry with different credentials? [y/N] ").strip().lower()
            if retry != "y":
                self.stderr.write("Aborted — no changes written to .env\n")
                return
            host, port, name, user, password = self._prompt_credentials(
                {"DB_HOST": host, "DB_PORT": port, "DB_NAME": name,
                 "DB_USER": user, "DB_PASSWORD": password}
            )

        # Write to .env
        env_file = find_dotenv(usecwd=True)
        if not env_file:
            env_file = str(Path.cwd() / ".env")
            self.stdout.write(
                self.style.WARNING(f"  No .env file found — creating {env_file}\n")
            )

        for key, value in [
            ("DB_HOST", host),
            ("DB_PORT", port),
            ("DB_NAME", name),
            ("DB_USER", user),
            ("DB_PASSWORD", password),
        ]:
            set_key(env_file, key, value)

        self.stdout.write(self.style.SUCCESS(f"\nWritten to {env_file}\n"))
        self.stdout.write(
            "Restart the server (or re-run migrations) for changes to take effect.\n"
        )

    # -----------------------------------------------------------------------
    # Prompting helpers
    # -----------------------------------------------------------------------

    def _prompt_credentials(self, current: dict) -> tuple:
        """Prompt for all five DB settings and return (host, port, name, user, password)."""
        host = self._prompt("Database host", current["DB_HOST"])
        port = self._prompt("Database port", current["DB_PORT"])
        name = self._prompt("Database name", current["DB_NAME"])
        user = self._prompt("Database user", current["DB_USER"])

        has_password = bool(current["DB_PASSWORD"])
        hint = "leave blank to keep existing" if has_password else "leave blank for none"
        raw = getpass.getpass(f"  Database password ({hint}): ")
        password = raw if raw else current["DB_PASSWORD"]

        return host, port, name, user, password

    def _prompt(self, label: str, default: str) -> str:
        result = input(f"  {label} [{default}]: ").strip()
        return result if result else default

    # -----------------------------------------------------------------------
    # Connection test
    # -----------------------------------------------------------------------

    def _test_connection(
        self, host: str, port: str, name: str, user: str, password: str
    ) -> str | None:
        """
        Attempt a direct MySQL connection.  Returns None on success, or an
        error message string on failure.

        Uses MySQLdb directly rather than Django's database layer so that this
        command is safe to run before migrations have been applied.
        """
        try:
            import MySQLdb
        except ImportError:
            return (
                "mysqlclient is not installed.  "
                "Run: pip install mysqlclient"
            )

        try:
            conn = MySQLdb.connect(
                host=host,
                port=int(port),
                db=name,
                user=user,
                passwd=password,
                connect_timeout=5,
            )
            conn.close()
            return None
        except MySQLdb.OperationalError as exc:
            # OperationalError args: (errno, message)
            code, msg = exc.args if len(exc.args) == 2 else (None, str(exc))
            if code == 1049:
                return (
                    f"Unknown database '{name}'. "
                    "Create it first: CREATE DATABASE {name} CHARACTER SET utf8mb4;"
                )
            if code in (1045, 1044):
                return f"Access denied for user '{user}'@'{host}' — check credentials."
            if code == 2003:
                return f"Cannot connect to MySQL server at {host}:{port} — is MariaDB running?"
            return f"MySQL error {code}: {msg}"
        except ValueError:
            return f"Invalid port number: '{port}'"
        except Exception as exc:
            return str(exc)
