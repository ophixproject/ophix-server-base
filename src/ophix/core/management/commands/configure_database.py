"""
ophix.core.management.commands.configure_database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interactively configure the database connection and write credentials to .env.

Prompts for each database setting, showing the current value as the default.
Tests the connection directly (bypassing Django's ORM) before writing anything,
so this command is safe to run before the database schema exists.

Live-tests MariaDB, MySQL, PostgreSQL, and CockroachDB (Postgres-wire-compatible).
SQL Server and Oracle are accepted but skip the live test - this wizard has no
tester for either; verify connectivity manually after writing .env. Set DB_ENGINE
to select the backend.

TLS is optional.  If a CA certificate path is supplied, TLS is enabled.
Mutual TLS (client certificate authentication) is a further opt-in.

Usage::

    ophix-manage configure_database
"""

import getpass
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from dotenv import find_dotenv, set_key


class Command(BaseCommand):
    help = (
        "Interactively configure and test the database connection, "
        "writing credentials to .env on success"
    )

    def handle(self, *args, **options):
        try:
            self._handle(*args, **options)
        except KeyboardInterrupt:
            self.stdout.write("")
            self.stdout.write("Cancelled.")
            raise SystemExit(1)

    def _handle(self, *args, **options):
        self.stdout.write("\nConfigure database connection\n")
        self.stdout.write("=" * 40 + "\n")
        self.stdout.write("Press Enter to keep the current value shown in [brackets].\n\n")

        # --- Engine ---
        current_engine = os.getenv("DB_ENGINE", "mariadb").lower()
        engine = self._prompt_engine(current_engine)

        # Default port depends on engine; snap if currently at a known default.
        _DEFAULT_PORTS = {
            "postgres": "5432", "sqlserver": "1433", "oracle": "1521", "cockroachdb": "26257",
        }
        current_port = os.getenv("DB_PORT", "")
        if not current_port or current_port in ("3306", *_DEFAULT_PORTS.values()):
            current_port = _DEFAULT_PORTS.get(engine, "3306")

        current = {
            "DB_HOST":     os.getenv("DB_HOST", "localhost"),
            "DB_PORT":     current_port,
            "DB_NAME":     os.getenv("DB_NAME", "ophix_db"),
            "DB_USER":     os.getenv("DB_USER", "ophixuser"),
            "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
        }
        current_tls = {
            "DB_SSL_CA":   os.getenv("DB_SSL_CA", ""),
            "DB_SSL_CERT": os.getenv("DB_SSL_CERT", ""),
            "DB_SSL_KEY":  os.getenv("DB_SSL_KEY", ""),
        }

        host, port, name, user, password = self._prompt_credentials(current)
        ssl_ca, ssl_cert, ssl_key = self._prompt_tls(current_tls)

        # Test → retry loop
        _UNTESTABLE_ENGINES = ("sqlserver", "oracle")
        while True:
            if engine in _UNTESTABLE_ENGINES:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nSkipping live connection test — '{engine}' is not supported by "
                        "this wizard's tester.\n  Verify connectivity manually (e.g. "
                        "ophix-manage migrate) after writing .env.\n"
                    )
                )
                break

            self.stdout.write("\nTesting connection... ")
            self.stdout.flush()
            error = self._test_connection(engine, host, port, name, user, password,
                                          ssl_ca, ssl_cert, ssl_key)
            if error is None:
                self.stdout.write(self.style.SUCCESS("OK\n"))
                break

            self.stdout.write(self.style.ERROR("FAILED\n"))
            self.stderr.write(f"  {error}\n\n")
            retry = input("Retry with different settings? [y/N] ").strip().lower()
            if retry != "y":
                self.stderr.write("Aborted — no changes written to .env\n")
                return
            engine = self._prompt_engine(engine)
            host, port, name, user, password = self._prompt_credentials(
                {"DB_HOST": host, "DB_PORT": port, "DB_NAME": name,
                 "DB_USER": user, "DB_PASSWORD": password}
            )
            ssl_ca, ssl_cert, ssl_key = self._prompt_tls(
                {"DB_SSL_CA": ssl_ca, "DB_SSL_CERT": ssl_cert, "DB_SSL_KEY": ssl_key}
            )

        # Write to .env
        env_file = find_dotenv(usecwd=True)
        if not env_file:
            env_file = str(Path.cwd() / ".env")
            self.stdout.write(
                self.style.WARNING(f"  No .env file found — creating {env_file}\n")
            )

        for key, value in [
            ("DB_ENGINE",   engine),
            ("DB_HOST",     host),
            ("DB_PORT",     port),
            ("DB_NAME",     name),
            ("DB_USER",     user),
            ("DB_PASSWORD", password),
            ("DB_SSL_CA",   ssl_ca),
            ("DB_SSL_CERT", ssl_cert),
            ("DB_SSL_KEY",  ssl_key),
        ]:
            set_key(env_file, key, value, quote_mode="always")

        self.stdout.write(self.style.SUCCESS(f"\nWritten to {env_file}\n"))
        self.stdout.write(
            "Restart the server (or re-run migrations) for changes to take effect.\n"
        )

    # -----------------------------------------------------------------------
    # Prompting helpers
    # -----------------------------------------------------------------------

    def _prompt_engine(self, current: str) -> str:
        _VALID_ENGINES = ("mariadb", "mysql", "postgres", "sqlserver", "oracle", "cockroachdb")
        self.stdout.write("Database engine\n")
        self.stdout.write("-" * 40 + "\n")
        self.stdout.write(f"  Valid values: {', '.join(_VALID_ENGINES)}\n")
        self.stdout.write("  Extra engines require the matching ophix-dbengine-* plugin.\n")
        engine = self._prompt("Database engine", current).lower()
        if engine not in _VALID_ENGINES:
            self.stdout.write(
                self.style.WARNING(f"  Unknown engine '{engine}' — defaulting to mariadb\n")
            )
            engine = "mariadb"
        self.stdout.write("\n")
        return engine

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

    def _prompt_tls(self, current: dict) -> tuple[str, str, str]:
        """
        Prompt for optional TLS settings.

        Returns (ssl_ca, ssl_cert, ssl_key) — empty strings when not in use.
        TLS is enabled only when ssl_ca is non-empty.
        Mutual TLS (ssl_cert + ssl_key) is a further opt-in after TLS is enabled.
        """
        self.stdout.write("\nDatabase TLS\n")
        self.stdout.write("-" * 40 + "\n")

        current_ca = current.get("DB_SSL_CA", "")
        currently_tls = bool(current_ca)
        tls_indicator = "Y/n" if currently_tls else "y/N"
        use_tls = input(f"  Use TLS for the database connection? [{tls_indicator}]: ").strip().lower()

        if currently_tls:
            tls_enabled = use_tls not in ("n", "no")
        else:
            tls_enabled = use_tls in ("y", "yes")

        if not tls_enabled:
            if currently_tls:
                self.stdout.write(self.style.WARNING("  TLS disabled — clearing existing SSL settings.\n"))
            return "", "", ""

        ssl_ca = self._prompt("  CA certificate path", current_ca)
        if not ssl_ca:
            self.stdout.write(self.style.WARNING("  No CA path entered — TLS not enabled.\n"))
            return "", "", ""

        if not Path(ssl_ca).exists():
            self.stdout.write(self.style.WARNING(f"  Warning: {ssl_ca} does not exist\n"))

        current_cert = current.get("DB_SSL_CERT", "")
        currently_mtls = bool(current_cert)
        mtls_indicator = "Y/n" if currently_mtls else "y/N"
        use_mtls = input(f"  Use mutual TLS (client certificate auth)? [{mtls_indicator}]: ").strip().lower()

        if currently_mtls:
            mtls_enabled = use_mtls not in ("n", "no")
        else:
            mtls_enabled = use_mtls in ("y", "yes")

        if not mtls_enabled:
            return ssl_ca, "", ""

        current_key = current.get("DB_SSL_KEY", "")
        ssl_cert = self._prompt("  Client certificate path", current_cert)
        ssl_key  = self._prompt("  Client key path", current_key)

        for label, path in [("Client certificate", ssl_cert), ("Client key", ssl_key)]:
            if path and not Path(path).exists():
                self.stdout.write(self.style.WARNING(f"  Warning: {label} path {path} does not exist\n"))

        return ssl_ca, ssl_cert, ssl_key

    def _prompt(self, label: str, default: str) -> str:
        result = input(f"  {label} [{default}]: ").strip()
        return result if result else default

    # -----------------------------------------------------------------------
    # Connection test
    # -----------------------------------------------------------------------

    def _test_connection(
        self,
        engine: str,
        host: str, port: str, name: str, user: str, password: str,
        ssl_ca: str = "", ssl_cert: str = "", ssl_key: str = "",
    ) -> str | None:
        # CockroachDB is Postgres-wire-compatible - reuse the same tester.
        if engine in ("postgres", "cockroachdb"):
            return self._test_postgres(host, port, name, user, password,
                                       ssl_ca, ssl_cert, ssl_key)
        return self._test_mysql(host, port, name, user, password,
                                ssl_ca, ssl_cert, ssl_key)

    def _test_mysql(
        self,
        host: str, port: str, name: str, user: str, password: str,
        ssl_ca: str = "", ssl_cert: str = "", ssl_key: str = "",
    ) -> str | None:
        """
        Attempt a direct MySQL/MariaDB connection. Returns None on success,
        or an error message string on failure.
        """
        try:
            import MySQLdb
        except ImportError:
            return "mysqlclient is not installed.  Run: pip install mysqlclient"

        kwargs = dict(
            host=host,
            port=int(port),
            db=name,
            user=user,
            passwd=password,
            connect_timeout=5,
        )

        if ssl_ca:
            ssl_dict = {"ca": ssl_ca}
            if ssl_cert:
                ssl_dict["cert"] = ssl_cert
            if ssl_key:
                ssl_dict["key"] = ssl_key
            kwargs["ssl"] = ssl_dict

        try:
            conn = MySQLdb.connect(**kwargs)
            conn.close()
            return None
        except MySQLdb.OperationalError as exc:
            code, msg = exc.args if len(exc.args) == 2 else (None, str(exc))
            if code == 1049:
                return (
                    f"Unknown database '{name}'. "
                    f"Create it first: CREATE DATABASE {name} CHARACTER SET utf8mb4;"
                )
            if code in (1045, 1044):
                return f"Access denied for user '{user}'@'{host}' — check credentials."
            if code == 2003:
                return f"Cannot connect to MySQL server at {host}:{port} — is MariaDB running?"
            if code == 2026:
                return "TLS/SSL connection error — check CA certificate path and server TLS configuration."
            return f"MySQL error {code}: {msg}"
        except ValueError:
            return f"Invalid port number: '{port}'"
        except Exception as exc:
            return str(exc)

    def _test_postgres(
        self,
        host: str, port: str, name: str, user: str, password: str,
        ssl_ca: str = "", ssl_cert: str = "", ssl_key: str = "",
    ) -> str | None:
        """
        Attempt a direct PostgreSQL connection. Returns None on success,
        or an error message string on failure.
        """
        try:
            import psycopg2
        except ImportError:
            return "psycopg2 is not installed.  Run: pip install psycopg2-binary"

        kwargs = dict(
            host=host,
            port=int(port),
            dbname=name,
            user=user,
            password=password,
            connect_timeout=5,
        )

        if ssl_ca:
            kwargs["sslmode"] = "verify-ca"
            kwargs["sslrootcert"] = ssl_ca
            if ssl_cert:
                kwargs["sslcert"] = ssl_cert
            if ssl_key:
                kwargs["sslkey"] = ssl_key

        try:
            conn = psycopg2.connect(**kwargs)
            conn.close()
            return None
        except psycopg2.OperationalError as exc:
            msg = str(exc).strip()
            if "does not exist" in msg:
                return f"Database '{name}' does not exist. Create it first: CREATE DATABASE {name};"
            if "password authentication failed" in msg or "role" in msg:
                return f"Access denied for user '{user}'@'{host}' — check credentials."
            if "Connection refused" in msg or "could not connect" in msg:
                return f"Cannot connect to PostgreSQL at {host}:{port} — is PostgreSQL running?"
            if "SSL" in msg or "certificate" in msg.lower():
                return "TLS/SSL connection error — check CA certificate path and server TLS configuration."
            return f"PostgreSQL error: {msg}"
        except ValueError:
            return f"Invalid port number: '{port}'"
        except Exception as exc:
            return str(exc)
