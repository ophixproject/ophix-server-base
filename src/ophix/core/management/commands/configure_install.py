"""
ophix.core.management.commands.configure_install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interactive first-run configuration wizard for an Ophix server.

Collects all required settings (install directory, TLS certificates,
database connection, superuser credentials, admin theme) and writes:
  - .<server_name>.conf  -- machine-readable install config (read by run_install)
  - .env                 -- Django environment settings (ready for use)

Idempotent: existing values in .<server_name>.conf are used as defaults
on re-run so you can update individual settings without re-entering everything.

Usage::

    ophix-manage configure_install credserver
    ophix-manage configure_install confserver
"""

import configparser
import getpass
import importlib.util
import os
import socket
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ophix.core.management.commands.generate_deploy_config import (
    _discover_domain_version,
    _discover_plugin_fragments,
    _render_template,
    _slugify,
)


# ---------------------------------------------------------------------------
# Plugin hook discovery
# ---------------------------------------------------------------------------

def _call_plugin_configure_hooks(conf, command):
    """
    Call install_configure(conf, command) on each installed ophix plugin that
    exposes it. Plugins use this to prompt for or generate plugin-specific
    settings (e.g. encryption keys) and store them in a plugin section of conf.
    """
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="ophix.plugins")
    except Exception:
        return

    for ep in eps:
        try:
            mod = importlib.import_module(ep.value)
        except Exception:
            continue
        hook = getattr(mod, "install_configure", None)
        if callable(hook):
            command.stdout.write(f"--- {ep.name} ---\n")
            try:
                hook(conf, command)
            except Exception as exc:
                command.stdout.write(
                    command.style.WARNING(f"  Plugin hook error ({ep.name}): {exc}\n")
                )
            command.stdout.write("\n")


# ---------------------------------------------------------------------------
# Certificate validation
# ---------------------------------------------------------------------------

def _validate_cert_hostname(cert_path: str, hostname: str):
    """
    Returns None if cert covers hostname, else a warning string.
    Returns None also if cryptography package is unavailable (check skipped).
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        return None

    try:
        data = Path(cert_path).read_bytes()
        try:
            cert = x509.load_pem_x509_certificate(data, default_backend())
        except Exception:
            cert = x509.load_der_x509_certificate(data, default_backend())
    except Exception as exc:
        return f"Could not parse certificate: {exc}"

    names = []
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        names.extend(san.value.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        pass

    if not names:
        try:
            cn_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn_attrs:
                names.append(cn_attrs[0].value)
        except Exception:
            pass

    def _matches(name, host):
        if name.startswith("*."):
            parts = host.split(".")
            return len(parts) >= 2 and ".".join(parts[1:]) == name[2:]
        return name.lower() == host.lower()

    if any(_matches(n, hostname) for n in names):
        return None
    listed = ", ".join(names) if names else "none"
    return f"Certificate does not cover '{hostname}'. Names in cert: {listed}"


# ---------------------------------------------------------------------------
# Theme detection (package-based, no DB required)
# ---------------------------------------------------------------------------

def _detect_installed_theme_names():
    """
    Discover theme names from installed ophix theme packages without a DB query.
    Looks for themes/<Name>/theme.json under each plugin's package directory.
    """
    themes = []
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="ophix.plugins")
    except Exception:
        return themes

    for ep in eps:
        spec = importlib.util.find_spec(ep.value)
        if not spec or not spec.origin:
            continue
        theme_dir = Path(spec.origin).parent / "themes"
        if not theme_dir.is_dir():
            continue
        for d in sorted(theme_dir.iterdir()):
            if d.is_dir() and (d / "theme.json").exists():
                themes.append(d.name)

    return themes


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Interactive first-run configuration wizard. "
        "Writes .<server_name>.conf and .env."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "server_name",
            help="Short slug for this server (e.g. credserver, confserver, certserver)",
        )

    def handle(self, *args, **options):
        server_name = options["server_name"].lower().strip()
        conf_path = Path.cwd() / f".{server_name}.conf"

        conf = configparser.ConfigParser()
        if conf_path.exists():
            conf.read(str(conf_path))
            self.stdout.write(
                self.style.WARNING(
                    f"\nLoaded existing configuration from {conf_path}\n"
                    "Press Enter to keep each value shown in [brackets].\n"
                )
            )
        else:
            self.stdout.write(f"\nConfiguring new Ophix server: {server_name}\n")
            self.stdout.write("Press Enter to accept each default shown in [brackets].\n")

        self.stdout.write("=" * 60 + "\n\n")

        for section in ("server", "tls", "database", "superuser", "admin"):
            if not conf.has_section(section):
                conf.add_section(section)

        dist_name, domain_ver = _discover_domain_version()
        if dist_name:
            self.stdout.write(
                self.style.SUCCESS(f"  Domain plugin detected: {dist_name} {domain_ver or ''}\n\n")
            )
        else:
            self.stdout.write(
                self.style.WARNING("  No domain plugin detected. Install a domain package first.\n\n")
            )

        # ------------------------------------------------------------------ #
        # [server]
        # ------------------------------------------------------------------ #
        self.stdout.write("--- Server ---\n")

        default_install = conf.get("server", "install_dir", fallback=str(Path.cwd()))
        install_dir = self._prompt("Install directory", default_install)
        conf.set("server", "install_dir", install_dir)

        default_host = conf.get("server", "hostname", fallback=socket.getfqdn())
        hostname = self._prompt("Server hostname (FQDN)", default_host)
        conf.set("server", "hostname", hostname)

        default_http_redirect = conf.getboolean("server", "http_redirect", fallback=True)
        http_redirect = self._prompt_bool(
            "Enable HTTP→HTTPS redirect on port 80?",
            "Disable if another process (e.g. Apache) already owns port 80.",
            default_http_redirect,
        )
        conf.set("server", "http_redirect", "yes" if http_redirect else "no")

        default_svc_user = conf.get("server", "service_user", fallback="ophix")
        service_user = self._prompt("Service user", default_svc_user)
        conf.set("server", "service_user", service_user)

        default_svc_group = conf.get("server", "service_group", fallback=service_user)
        service_group = self._prompt("Service group", default_svc_group)
        conf.set("server", "service_group", service_group)

        self.stdout.write("\n")

        # ------------------------------------------------------------------ #
        # [tls]
        # ------------------------------------------------------------------ #
        self.stdout.write("--- TLS Certificates ---\n")
        self.stdout.write(
            "  Provide source paths on this machine.\n"
            "  run_install will copy them into the install directory.\n\n"
        )

        cert_path = self._prompt_path(
            "TLS certificate (.crt / .pem)",
            conf.get("tls", "cert_path", fallback=""),
            required=True,
        )
        if cert_path:
            err = _validate_cert_hostname(cert_path, hostname)
            if err is None:
                self.stdout.write(self.style.SUCCESS(f"  Certificate covers {hostname}\n"))
            elif err:
                self.stdout.write(self.style.WARNING(f"  Warning: {err}\n"))
        conf.set("tls", "cert_path", cert_path)

        key_path = self._prompt_path(
            "TLS private key (.key / .pem)",
            conf.get("tls", "key_path", fallback=""),
            required=True,
        )
        conf.set("tls", "key_path", key_path)

        ca_bundle = self._prompt_path(
            "CA bundle for nginx ssl_trusted_certificate (optional, press Enter to skip)",
            conf.get("tls", "ca_bundle", fallback=""),
            required=False,
        )
        conf.set("tls", "ca_bundle", ca_bundle)

        self.stdout.write("\n")

        # ------------------------------------------------------------------ #
        # [database]
        # ------------------------------------------------------------------ #
        self.stdout.write("--- Database ---\n")

        from ophix.core.management.commands.configure_database import Command as CfgDB
        db_cmd = CfgDB()
        db_cmd.stdout = self.stdout
        db_cmd.stderr = self.stderr
        db_cmd.style = self.style

        current_engine = conf.get(
            "database", "engine", fallback=os.getenv("DB_ENGINE", "mariadb")
        ).lower()
        engine = db_cmd._prompt_engine(current_engine)

        current_port = conf.get("database", "port", fallback="")
        if not current_port or current_port in ("3306", "5432"):
            current_port = "5432" if engine == "postgres" else "3306"

        db_current = {
            "DB_HOST":     conf.get("database", "host", fallback="localhost"),
            "DB_PORT":     current_port,
            "DB_NAME":     conf.get("database", "name", fallback="ophix_db"),
            "DB_USER":     conf.get("database", "user", fallback="ophixuser"),
            "DB_PASSWORD": conf.get("database", "password", fallback=""),
        }
        db_tls = {
            "DB_SSL_CA":   conf.get("database", "ssl_ca", fallback=""),
            "DB_SSL_CERT": conf.get("database", "ssl_cert", fallback=""),
            "DB_SSL_KEY":  conf.get("database", "ssl_key", fallback=""),
        }

        while True:
            host, port, name, user, password = db_cmd._prompt_credentials(db_current)
            ssl_ca, ssl_cert, ssl_key = db_cmd._prompt_tls(db_tls)

            self.stdout.write("\nTesting database connection... ")
            self.stdout.flush()
            error = db_cmd._test_connection(
                engine, host, port, name, user, password, ssl_ca, ssl_cert, ssl_key
            )
            if error is None:
                self.stdout.write(self.style.SUCCESS("OK\n\n"))
                break
            self.stdout.write(self.style.ERROR("FAILED\n"))
            self.stderr.write(f"  {error}\n\n")
            retry = input("Retry with different settings? [y/N] ").strip().lower()
            if retry != "y":
                raise CommandError("Aborted — database connection failed. Nothing written.")
            db_current = {
                "DB_HOST": host, "DB_PORT": port, "DB_NAME": name,
                "DB_USER": user, "DB_PASSWORD": password,
            }
            db_tls = {"DB_SSL_CA": ssl_ca, "DB_SSL_CERT": ssl_cert, "DB_SSL_KEY": ssl_key}

        conf.set("database", "engine", engine)
        conf.set("database", "host", host)
        conf.set("database", "port", port)
        conf.set("database", "name", name)
        conf.set("database", "user", user)
        conf.set("database", "password", password)
        conf.set("database", "ssl_ca", ssl_ca)
        conf.set("database", "ssl_cert", ssl_cert)
        conf.set("database", "ssl_key", ssl_key)

        # ------------------------------------------------------------------ #
        # [superuser]
        # ------------------------------------------------------------------ #
        self.stdout.write("--- Superuser ---\n")

        su_user = self._prompt(
            "Superuser username", conf.get("superuser", "username", fallback="admin")
        )
        conf.set("superuser", "username", su_user)

        su_email = self._prompt(
            "Superuser email", conf.get("superuser", "email", fallback="")
        )
        conf.set("superuser", "email", su_email)

        has_pw = bool(conf.get("superuser", "password", fallback=""))
        pw_hint = "leave blank to keep existing" if has_pw else "required"
        while True:
            su_pw = getpass.getpass(f"  Superuser password ({pw_hint}): ")
            if su_pw:
                su_pw2 = getpass.getpass("  Confirm password: ")
                if su_pw != su_pw2:
                    self.stdout.write(self.style.ERROR("  Passwords do not match — try again.\n"))
                    continue
                conf.set("superuser", "password", su_pw)
                break
            elif has_pw:
                break
            else:
                self.stdout.write(self.style.ERROR("  Password is required.\n"))

        self.stdout.write("\n")

        # ------------------------------------------------------------------ #
        # [admin]
        # ------------------------------------------------------------------ #
        self.stdout.write("--- Admin UI ---\n")

        themes = _detect_installed_theme_names()
        existing_theme = conf.get("admin", "activate_theme", fallback="")
        if themes:
            self.stdout.write(f"  Available themes: {', '.join(themes)}\n")
            default_theme = existing_theme if existing_theme in themes else themes[0]
            activate_theme = self._prompt(
                "Theme to activate (press Enter to skip)", default_theme
            )
        else:
            activate_theme = ""

        conf.set("admin", "activate_theme", activate_theme)

        default_title = conf.get("admin", "admin_title", fallback="Ophix Admin")
        admin_title = self._prompt("Admin site title", default_title)
        conf.set("admin", "admin_title", admin_title)

        self.stdout.write("\n")

        # ------------------------------------------------------------------ #
        # Plugin configure hooks
        # ------------------------------------------------------------------ #
        _call_plugin_configure_hooks(conf, self)

        # ------------------------------------------------------------------ #
        # Write conf file
        # ------------------------------------------------------------------ #
        with open(str(conf_path), "w") as fh:
            conf.write(fh)
        try:
            os.chmod(str(conf_path), 0o600)
        except OSError:
            pass
        self.stdout.write(self.style.SUCCESS(f"Written: {conf_path}\n"))

        # ------------------------------------------------------------------ #
        # Write .env
        # ------------------------------------------------------------------ #
        self._write_env(
            server_name=server_name,
            install_dir=install_dir,
            hostname=hostname,
            domain_ver=domain_ver,
            engine=engine,
            db_host=host,
            db_port=port,
            db_name=name,
            db_user=user,
            db_password=password,
            db_ssl_ca=ssl_ca,
            db_ssl_cert=ssl_cert,
            db_ssl_key=ssl_key,
        )

        self.stdout.write(
            self.style.SUCCESS("\nConfiguration complete.\n")
            + f"\nNext step: ophix-manage run_install {server_name}\n"
        )

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #

    def _write_env(
        self, server_name, install_dir, hostname, domain_ver,
        engine, db_host, db_port, db_name, db_user, db_password,
        db_ssl_ca, db_ssl_cert, db_ssl_key,
    ):
        from django.conf import settings as django_settings

        slug = _slugify(server_name)
        static_root = str(getattr(django_settings, "STATIC_ROOT", Path(install_dir) / "static"))
        ctx = {
            "portal_name": slug,
            "install_dir": install_dir,
            "server_name": server_name,
            "static_root": static_root,
            "media_root": str(Path(install_dir) / "media"),
            "venv_path": sys.prefix,
            "domain_version": domain_ver or "",
        }

        content = _render_template("env.sample.j2", ctx)
        fragments = _discover_plugin_fragments(ctx)
        if fragments:
            content += "\n"
            for plugin_name, frag in fragments:
                content += (
                    f"\n# {'=' * 70}\n"
                    f"# Plugin: {plugin_name}\n"
                    f"# {'=' * 70}\n\n"
                )
                content += frag.lstrip("\n")

        env_path = Path.cwd() / ".env"
        env_path.write_text(content, encoding="utf-8")
        try:
            os.chmod(str(env_path), 0o600)
        except OSError:
            pass

        from dotenv import set_key
        pairs = [
            ("SERVER_NAME",   getattr(django_settings, "SERVER_NAME", server_name)),
            ("SERVER_VERSION", domain_ver or ""),
            ("INSTALL_DIR",   install_dir),
            ("ALLOWED_HOSTS", hostname),
            ("DB_ENGINE",     engine),
            ("DB_HOST",       db_host),
            ("DB_PORT",       db_port),
            ("DB_NAME",       db_name),
            ("DB_USER",       db_user),
            ("DB_PASSWORD",   db_password),
            ("DB_SSL_CA",     db_ssl_ca),
            ("DB_SSL_CERT",   db_ssl_cert),
            ("DB_SSL_KEY",    db_ssl_key),
        ]
        for key, value in pairs:
            set_key(str(env_path), key, value, quote_mode="never")

        self.stdout.write(self.style.SUCCESS(f"Written: {env_path}\n"))

    def _prompt(self, label, default):
        result = input(f"  {label} [{default}]: ").strip()
        return result if result else default

    def _prompt_bool(self, label, hint, default):
        indicator = "[Y/n]" if default else "[y/N]"
        if hint:
            self.stdout.write(f"  {hint}\n")
        result = input(f"  {label} {indicator}: ").strip().lower()
        if not result:
            return default
        return result in ("y", "yes")

    def _prompt_path(self, label, default, required=True):
        # Enable tab completion for file paths on Linux (readline not available on Windows).
        _readline_active = False
        try:
            import glob as _glob
            import readline as _rl

            def _path_completer(text, state):
                return (_glob.glob(text + "*") + [None])[state]

            _rl.set_completer(_path_completer)
            _rl.set_completer_delims(" \t\n;")
            _rl.parse_and_bind("tab: complete")
            _readline_active = True
        except ImportError:
            pass

        try:
            while True:
                result = self._prompt(label, default)
                if not result:
                    if not required:
                        return ""
                    self.stdout.write(self.style.ERROR(f"  {label} is required.\n"))
                    continue
                try:
                    exists = Path(result).exists()
                except (PermissionError, OSError):
                    # Can't verify the path (e.g. no read permission on parent dir).
                    # Ask to confirm rather than crashing.
                    exists = False
                if not exists:
                    self.stdout.write(self.style.WARNING(f"  Warning: {result} does not exist or is not accessible.\n"))
                    confirm = input("  Use this path anyway? [y/N]: ").strip().lower()
                    if confirm == "y":
                        return result
                    default = result
                    continue
                return result
        finally:
            if _readline_active:
                try:
                    _rl.set_completer(None)
                except Exception:
                    pass
