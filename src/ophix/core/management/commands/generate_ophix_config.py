"""
ophix.core.management.commands.generate_ophix_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generate deployment configuration files for an Ophix server.

Produces any combination of:
  .env.sample           -- annotated sample environment file, with plugin
                           env fragments automatically appended
  <slug>.nginx.conf     -- nginx server blocks (HTTP redirect + HTTPS proxy)
  <slug>.service        -- systemd unit file for gunicorn

Plugin env fragments
--------------------
Any installed ophix plugin that ships a ``deploy_templates/env.fragment.j2``
file will have its variables automatically appended to the generated .env.sample.
This means domain plugins (ophix-confs, ophix-certs, etc.) and optional plugins
(ophix-docs, etc.) can each describe their own settings without ophix-server-base
needing to know about them.

Usage::

    ophix-manage generate_ophix_config --all \\
        --server-hostname credserver.example.com \\
        --service-user ophix

    ophix-manage generate_ophix_config --nginx --systemd \\
        --server-hostname credserver.example.com \\
        --service-user ophix --output-dir /tmp

    ophix-manage generate_ophix_config --env

    # After adding a new plugin to an existing install:
    ophix-manage generate_ophix_config --append
"""

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "deploy_templates"

# ---------------------------------------------------------------------------
# Installation guide shown with --help
# ---------------------------------------------------------------------------

EPILOG = """
BOOTSTRAP GUIDE
===============
The recommended way to deploy a fresh Ophix server is the guided installer:

   ophix-manage configure_install <slug>   # interactive wizard
   ophix-manage run_install <slug>         # runs migrate, collectstatic, creates superuser
   sudo bash <slug>_sudo_install.sh        # sets ownership, installs nginx + systemd

Where <slug> is a short name for this server instance (e.g. credserver, confserver).

MANUAL BOOTSTRAP (advanced)
============================
Use generate_ophix_config if you prefer to manage each step yourself.

1. Generate deployment files
   ophix-manage generate_ophix_config --all \\
       --server-hostname your.server.hostname \\
       --service-user ophix

2. Edit the sample env file
   cp .env.sample .env
   chmod 600 .env
   Edit .env — at minimum set:
     SERVER_NAME        human-readable label for the admin header
     INSTALL_DIR        runtime data directory (logs, media, socket, SSL)
     ALLOWED_HOSTS      comma-separated hostnames/IPs
     DB_*               database credentials (or use configure_database below)
   Leave DJANGO_SECRET_KEY blank — it is auto-generated on first run.

3. Configure and test the database interactively
   ophix-manage configure_database

4. Initialise the runtime directory structure
   ophix-manage init_deploy

5. Install SSL certificates
   Place your certificate and private key at:
     $INSTALL_DIR/ssl/certs/<slug>.crt
     $INSTALL_DIR/ssl/private/<slug>.key
   If using ophix-certs, those tools will place them here.

6. Install the nginx configuration
   sudo cp <slug>.nginx.conf /etc/nginx/sites-available/<slug>.conf
   sudo ln -s /etc/nginx/sites-available/<slug>.conf /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx

7. Install the systemd service
   sudo cp <slug>.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable <slug>

8. Run Django setup
   ophix-manage migrate
   ophix-manage collectstatic --noinput
   ophix-manage createsuperuser

9. Start the service
   sudo systemctl start <slug>
   sudo journalctl -u <slug> -f

ADDING A PLUGIN LATER
=====================
After installing a new ophix plugin into an existing deployment:

   pip install ophix-<plugin>
   ophix-manage generate_ophix_config --append

--append reads your existing .env, discovers all installed plugin fragments,
and appends any variables not already present.  Your existing values are
never modified.

SECURITY NOTES
==============
- chmod 600 .env — the .env file contains database credentials and the secret key
- Set DEBUG=False in production (it is False by default)
- Set AUTH_LEAK_INFO=False in production (it is False by default)
- If deployed behind a load balancer, the LB must strip and re-set
  X-Forwarded-For before requests reach nginx.  Without this, clients on an
  internal network could spoof their source IP and bypass token authentication.
- Tighten ALLOWED_HOSTS to explicit hostnames before going to production.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a SERVER_NAME string to a filesystem-safe slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _resolve_output_dir(requested: str | None) -> Path:
    """
    Choose an output directory in priority order:
      1. --output-dir if specified
      2. INSTALL_DIR from settings if it exists and is writable
      3. venv root (sys.prefix)
      4. current working directory
    """
    if requested:
        p = Path(requested)
        p.mkdir(parents=True, exist_ok=True)
        return p

    install_dir = getattr(settings, "INSTALL_DIR", None)
    if install_dir:
        p = Path(install_dir)
        if p.exists():
            probe = p / ".ophix_write_probe"
            try:
                probe.touch()
                probe.unlink()
                return p
            except OSError:
                pass

    return Path(sys.prefix)


def _render_template(name: str, ctx: dict, strict: bool = True) -> str:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined if strict else Undefined,
        keep_trailing_newline=True,
    )
    return env.get_template(name).render(**ctx)


def _render_fragment(fragment_path: Path, ctx: dict) -> str:
    """Render a plugin env fragment using a non-strict Jinja2 env."""
    from jinja2 import Environment, FileSystemLoader, Undefined
    env = Environment(
        loader=FileSystemLoader(str(fragment_path.parent)),
        undefined=Undefined,
        keep_trailing_newline=True,
    )
    return env.get_template(fragment_path.name).render(**ctx)


def _discover_plugin_fragments(ctx: dict) -> list[tuple[str, str]]:
    """
    Discover env.fragment.j2 files from all installed ophix plugins.

    Iterates over the ``ophix.plugins`` entry point group and looks for
    a ``deploy_templates/env.fragment.j2`` file in each plugin package.
    Returns a list of (plugin_name, rendered_content) tuples.
    """
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="ophix.plugins")
    except Exception:
        return []

    results = []
    for ep in eps:
        module_name = ep.value
        spec = importlib.util.find_spec(module_name)
        if not spec or not spec.origin:
            continue
        fragment_path = Path(spec.origin).parent / "deploy_templates" / "env.fragment.j2"
        if not fragment_path.exists():
            continue
        try:
            content = _render_fragment(fragment_path, ctx)
            results.append((ep.name, content))
        except Exception as exc:
            results.append((ep.name, f"# Error rendering env fragment for {ep.name}: {exc}\n"))

    return results


def _parse_env_keys(text: str) -> set[str]:
    """Return the set of variable names already defined in .env text."""
    keys = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _parse_all_keys(text: str) -> set[str]:
    """
    Return variable names from both active (KEY=val) and commented (# KEY=val) lines.
    Used to detect whether an opt-in (all-commented) fragment has already been appended.
    """
    keys = set()
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key and all(c.isalnum() or c == "_" for c in key):
                keys.add(key)
    return keys


def _get_env_value(text: str, key: str) -> str | None:
    """Return the current value of a specific key in .env text, or None if absent."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            if k.strip() == key:
                return v.strip()
    return None


def _discover_domain_version() -> tuple[str | None, str | None]:
    """
    Find the installed domain plugin and return (dist_name, version).

    A domain plugin is an AppConfig with ``is_ophix_domain = True``.
    Version is read from the plugin's ``_version.__version__`` attribute,
    which preserves the verbatim string from pyproject.toml (pip normalises
    leading zeroes away in distribution metadata, making 2026.04.12.01 become
    2026.4.12.1).  Falls back to importlib.metadata if _version.py is absent.

    Returns (dist_name, version) e.g. ('ophix-certs', '2026.04.12.01'),
    or (None, None) if no domain plugin is found or version cannot be determined.
    """
    try:
        import importlib
        from django.apps import apps as django_apps
        from importlib.metadata import packages_distributions

        domain_app = None
        for app_config in django_apps.get_app_configs():
            if getattr(app_config, "is_ophix_domain", False):
                domain_app = app_config
                break

        if domain_app is None:
            return None, None

        # packages_distributions() maps top-level module name → [dist_name, ...]
        pkg_map = packages_distributions()
        dists = pkg_map.get(domain_app.name, [])
        dist_name = dists[0] if dists else domain_app.name

        # Prefer _version.py (verbatim); fall back to normalised metadata version.
        try:
            version_mod = importlib.import_module(f"{domain_app.name}._version")
            return dist_name, version_mod.__version__
        except (ImportError, AttributeError):
            from importlib.metadata import version as pkg_version
            return dist_name, pkg_version(dist_name)

    except Exception:
        return None, None


def _filter_to_missing_blocks(content: str, existing_keys: set[str]) -> str:
    """
    Given rendered fragment content, return only the blocks whose keys are
    not already in existing_keys.

    A block is a run of consecutive non-blank lines.  An entire block is kept
    if at least one of its KEY= lines is not in existing_keys (so comments
    accompanying a new key are preserved).  Blocks where every key is already
    present are dropped.  Blank-line separators are preserved between kept blocks.
    """
    lines = content.splitlines(keepends=True)

    # Split into blocks (runs of non-blank lines) and separators (blank lines)
    segments = []
    current = []
    for line in lines:
        if line.strip() == "":
            if current:
                segments.append(("block", current))
                current = []
            segments.append(("blank", [line]))
        else:
            current.append(line)
    if current:
        segments.append(("block", current))

    kept = []
    for kind, seg_lines in segments:
        if kind == "blank":
            kept.append(seg_lines)
            continue
        # Extract all KEY= names in this block
        block_keys = set()
        for line in seg_lines:
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                block_keys.add(s.split("=", 1)[0].strip())
        if not block_keys:
            # Comment-only block — keep it (it's a section header)
            kept.append(seg_lines)
        elif not block_keys.issubset(existing_keys):
            # At least one key is new
            kept.append(seg_lines)
        # else: every key already present — drop

    # Collapse multiple consecutive blank lines to one
    result_lines = []
    prev_blank = False
    for seg_lines in kept:
        is_blank = all(l.strip() == "" for l in seg_lines)
        if is_blank and prev_blank:
            continue
        result_lines.extend(seg_lines)
        prev_blank = is_blank

    return "".join(result_lines)


def _write_file(path: Path, content: str, force: bool, stdout) -> bool:
    """Write content to path. Returns True if written, False if skipped."""
    if path.exists() and not force:
        stdout.write(f"  Skipped (exists): {path}  -- use --force to overwrite\n")
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _check_system(stdout, style):
    """Warn about missing system tools without blocking generation."""
    missing = []
    if not shutil.which("nginx"):
        missing.append("nginx")
    gunicorn_bin = Path(sys.prefix) / "bin" / "gunicorn"
    if not gunicorn_bin.exists() and not shutil.which("gunicorn"):
        missing.append("gunicorn (not found in venv or PATH)")
    if missing:
        for m in missing:
            stdout.write(style.WARNING(f"  WARNING: {m} not found — install before starting the service\n"))


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Generate deployment configuration files (nginx, systemd, .env sample). "
        "Plugin env fragments are automatically discovered and appended."
    )

    def create_parser(self, prog_name, subcommand, **kwargs):
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        kwargs.setdefault("epilog", EPILOG)
        return super().create_parser(prog_name, subcommand, **kwargs)

    def add_arguments(self, parser):
        what = parser.add_argument_group("what to generate")
        what.add_argument(
            "--env", action="store_true",
            help="Generate .env.sample (base settings + all installed plugin settings)",
        )
        what.add_argument(
            "--nginx", action="store_true",
            help="Generate nginx configuration (HTTP redirect + HTTPS proxy)",
        )
        what.add_argument(
            "--systemd", action="store_true",
            help="Generate systemd service unit for gunicorn",
        )
        what.add_argument(
            "--all", dest="all_files", action="store_true",
            help="Generate all of the above",
        )
        what.add_argument(
            "--append", action="store_true",
            help=(
                "Append missing plugin variables to the existing .env file. "
                "Use after installing a new plugin into an existing deployment. "
                "Never modifies existing values."
            ),
        )

        opts = parser.add_argument_group("options")
        opts.add_argument(
            "--output-dir", metavar="DIR",
            help=(
                "Directory to write generated files into. "
                "Defaults to INSTALL_DIR if it exists and is writable, "
                "then the venv root."
            ),
        )
        opts.add_argument(
            "--server-hostname", metavar="HOSTNAME",
            help="Hostname for the nginx server_name directive (required for --nginx/--all)",
        )
        opts.add_argument(
            "--service-user", metavar="USER",
            help="Linux user that gunicorn will run as (required for --systemd/--all)",
        )
        opts.add_argument(
            "--service-group", metavar="GROUP",
            help="Linux group for the gunicorn service (defaults to --service-user value)",
        )
        opts.add_argument(
            "--portal-name", metavar="SLUG",
            help=(
                "Short slug used in filenames, log paths, and socket path. "
                "Defaults to SERVER_NAME lowercased with spaces replaced by dashes."
            ),
        )
        opts.add_argument(
            "--force", action="store_true",
            help="Overwrite existing files (default: skip and warn)",
        )

    def handle(self, *args, **options):
        try:
            from jinja2 import Environment  # noqa: F401
        except ImportError:
            raise CommandError(
                "Jinja2 is required for generate_ophix_config but is not installed. "
                "Run: pip install Jinja2"
            )

        # --append is a standalone mode
        if options["append"]:
            self._handle_append(options)
            return

        # Expand --all
        if options["all_files"]:
            options["env"] = options["nginx"] = options["systemd"] = True

        if not any([options["env"], options["nginx"], options["systemd"]]):
            raise CommandError(
                "Specify at least one of --env, --nginx, --systemd, --all, or --append. "
                "Run with --help for the full installation guide."
            )

        # Validate required args
        if options["nginx"] and not options.get("server_hostname"):
            raise CommandError("--server-hostname is required when generating nginx config")
        if options["systemd"] and not options.get("service_user"):
            raise CommandError("--service-user is required when generating systemd config")

        # Derive slug
        server_name = getattr(settings, "SERVER_NAME", "") or "ophix-server"
        slug = options.get("portal_name") or _slugify(server_name)

        # Resolve output directory
        output_dir = _resolve_output_dir(options.get("output_dir"))
        self.stdout.write(f"\nOutput directory: {output_dir}\n")

        # System checks
        _check_system(self.stdout, self.style)

        # Build shared template context
        install_dir = str(getattr(settings, "INSTALL_DIR", "/var/lib/ophix"))
        dist_name, domain_ver = _discover_domain_version()
        domain_version = domain_ver or ""
        if domain_version:
            self.stdout.write(f"  Domain plugin: {dist_name} {domain_ver}\n")
        ctx_base = {
            "portal_name": slug,
            "install_dir": install_dir,
            "server_name": server_name,
            "static_root": str(settings.STATIC_ROOT),
            "media_root": str(getattr(settings, "MEDIA_ROOT", f"{install_dir}/media")),
            "venv_path": sys.prefix,
            "domain_version": domain_version,
        }

        written = []
        skipped = []

        # --- .env.sample ---
        if options["env"]:
            content = _render_template("env.sample.j2", ctx_base)
            fragments = _discover_plugin_fragments(ctx_base)
            if fragments:
                content += "\n"
                for plugin_name, frag_content in fragments:
                    header = (
                        f"\n# {'=' * 70}\n"
                        f"# Plugin: {plugin_name}\n"
                        f"# {'=' * 70}\n\n"
                    )
                    content += header + frag_content.lstrip("\n")
                    self.stdout.write(f"  Appended fragment for plugin: {plugin_name}\n")

            dest = output_dir / ".env.sample"
            if _write_file(dest, content, options["force"], self.stdout):
                written.append(dest)
                self.stdout.write(self.style.SUCCESS(f"  Written:  {dest}\n"))
                self.stdout.write(
                    f"  Next:     cp {dest} {output_dir / '.env'} && "
                    f"chmod 600 {output_dir / '.env'}\n"
                )
            else:
                skipped.append(dest)

        # --- nginx config ---
        if options["nginx"]:
            ctx = {**ctx_base, "server_hostname": options["server_hostname"]}
            content = _render_template("nginx.conf.j2", ctx)
            dest = output_dir / f"{slug}.nginx.conf"
            if _write_file(dest, content, options["force"], self.stdout):
                written.append(dest)
                self.stdout.write(self.style.SUCCESS(f"  Written:  {dest}\n"))
                self.stdout.write(
                    f"  Install:  sudo cp {dest} /etc/nginx/sites-available/{slug}.conf\n"
                    f"            sudo ln -s /etc/nginx/sites-available/{slug}.conf"
                    f" /etc/nginx/sites-enabled/\n"
                    f"            sudo nginx -t && sudo systemctl reload nginx\n"
                )
            else:
                skipped.append(dest)

        # --- systemd service ---
        if options["systemd"]:
            service_user = options["service_user"]
            service_group = options.get("service_group") or service_user
            ctx = {
                **ctx_base,
                "description": server_name,
                "service_user": service_user,
                "service_group": service_group,
            }
            content = _render_template("gunicorn.service.j2", ctx)
            dest = output_dir / f"{slug}.service"
            if _write_file(dest, content, options["force"], self.stdout):
                written.append(dest)
                self.stdout.write(self.style.SUCCESS(f"  Written:  {dest}\n"))
                self.stdout.write(
                    f"  Install:  sudo cp {dest} /etc/systemd/system/\n"
                    f"            sudo systemctl daemon-reload\n"
                    f"            sudo systemctl enable {slug}\n"
                    f"            sudo systemctl start {slug}\n"
                )
            else:
                skipped.append(dest)

        # Summary
        self.stdout.write("\n")
        if written:
            self.stdout.write(
                self.style.SUCCESS(f"Generated {len(written)} file(s). ")
                + "Run --help for the full installation guide.\n"
            )
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(skipped)} existing file(s). Use --force to overwrite.\n"
                )
            )

    # -----------------------------------------------------------------------
    # --append mode
    # -----------------------------------------------------------------------

    def _handle_append(self, options):
        from dotenv import find_dotenv

        env_file_path = find_dotenv(usecwd=True)
        if not env_file_path:
            raise CommandError(
                "No .env file found in the current directory or its parents. "
                "Run generate_ophix_config --env first to create one."
            )

        env_file = Path(env_file_path)
        existing_text = env_file.read_text(encoding="utf-8")
        existing_keys = _parse_env_keys(existing_text)

        self.stdout.write(f"\nAppending missing variables to: {env_file}\n")
        self.stdout.write(f"  Found {len(existing_keys)} existing variable(s).\n\n")

        server_name = getattr(settings, "SERVER_NAME", "") or "ophix-server"
        install_dir = str(getattr(settings, "INSTALL_DIR", "/var/lib/ophix"))
        dist_name_ctx, domain_ver_ctx = _discover_domain_version()
        domain_version_ctx = domain_ver_ctx or ""
        ctx = {
            "portal_name": _slugify(server_name),
            "install_dir": install_dir,
            "server_name": server_name,
            "static_root": str(settings.STATIC_ROOT),
            "media_root": str(getattr(settings, "MEDIA_ROOT", f"{install_dir}/media")),
            "venv_path": sys.prefix,
            "domain_version": domain_version_ctx,
        }

        # Sources: base template first, then plugin fragments.
        # Each entry is (label, rendered_content).
        sources = []

        # --- Base env.sample.j2 ---
        try:
            base_content = _render_template("env.sample.j2", ctx, strict=False)
            sources.append(("ophix-server-base", base_content))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"  Could not render base env.sample.j2: {exc}\n"
            ))

        # --- Plugin fragments ---
        for plugin_name, frag_content in _discover_plugin_fragments(ctx):
            sources.append((plugin_name, frag_content))

        if not sources:
            self.stdout.write("No sources found — nothing to append.\n")
            return

        appended = []   # list of (label, [key, ...], is_comment_only)
        skipped = []
        additions = []

        # Track all keys seen in .env — active and commented — to detect opt-in blocks.
        existing_all_keys = _parse_all_keys(existing_text)

        for label, content in sources:
            filtered = _filter_to_missing_blocks(content, existing_keys)
            new_keys = [
                line.strip().split("=", 1)[0].strip()
                for line in filtered.splitlines()
                if line.strip() and not line.strip().startswith("#") and "=" in line
            ]
            is_comment_only = False
            if not new_keys:
                # Fragment may be entirely commented-out (opt-in settings block).
                # Append it if it contains variable names not yet seen anywhere in .env.
                frag_all_keys = _parse_all_keys(filtered)
                new_commented = sorted(frag_all_keys - existing_all_keys)
                if new_commented:
                    new_keys = new_commented
                    is_comment_only = True

            if new_keys:
                header = (
                    f"\n# {'=' * 70}\n"
                    f"# {label} (appended by generate_ophix_config --append)\n"
                    f"# {'=' * 70}\n\n"
                )
                additions.append(header + filtered.lstrip("\n"))
                appended.append((label, new_keys, is_comment_only))
                if not is_comment_only:
                    existing_keys.update(new_keys)
                existing_all_keys.update(new_keys)
            else:
                skipped.append(label)

        if additions:
            with env_file.open("a", encoding="utf-8") as f:
                for block in additions:
                    f.write(block)
            for label, new_keys, is_comment_only in appended:
                if is_comment_only:
                    self.stdout.write(self.style.SUCCESS(
                        f"  Appended settings block from {label}"
                        f" (all commented — fill in to activate):\n"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(f"  Appended from {label}:\n"))
                for key in new_keys:
                    prefix = "    # " if is_comment_only else "    "
                    self.stdout.write(f"{prefix}{key}\n")
        if skipped:
            for label in skipped:
                self.stdout.write(f"  All variables already present: {label}\n")

        if additions:
            all_new_keys = [key for _, keys, _ in appended for key in keys]
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone. {len(appended)} source(s) had new variables appended "
                    f"({len(all_new_keys)} variable(s) total).\n"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "Review the new variables in .env and set any that require "
                    "non-default values before restarting the server.\n"
                )
            )
        else:
            self.stdout.write("\nAll variables already present — no changes made.\n")

        # --- SERVER_VERSION: always update if domain version has changed ---
        dist_name, domain_ver = dist_name_ctx, domain_ver_ctx
        if domain_ver:
            new_version = domain_ver
            current_version = _get_env_value(env_file.read_text(encoding="utf-8"), "SERVER_VERSION")
            if current_version != new_version:
                from dotenv import set_key as dotenv_set_key
                dotenv_set_key(str(env_file), "SERVER_VERSION", new_version, quote_mode="never")
                if current_version:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"\nUpdated SERVER_VERSION: {current_version!r} → {new_version!r}\n"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"\nSet SERVER_VERSION={new_version}\n")
                    )
            else:
                self.stdout.write(f"\nSERVER_VERSION already up to date: {new_version}\n")
