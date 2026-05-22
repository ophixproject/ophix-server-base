"""
ophix-manage list_plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List all installed Ophix plugins discovered via the ``ophix.plugins``
entry point group.

Examples
--------
List plugin names only:
    ophix-manage list_plugins

List name, pip package, module, and version:
    ophix-manage list_plugins --details
"""

import importlib
from importlib.metadata import entry_points, metadata as dist_metadata

from django.core.management.base import BaseCommand

ENTRY_POINT_GROUP = "ophix.plugins"


def _get_plugin_version(module_name: str, ep) -> str:
    """
    Return the version string for a plugin module.

    Tries the module's own _version.__version__ first (the canonical source
    committed to every Ophix package).  Falls back to the distribution
    metadata version reported by pip so that third-party plugins without
    _version.py still show something useful.  Returns "unknown" if neither
    is available.
    """
    try:
        version_mod = importlib.import_module(f"{module_name}._version")
        return version_mod.__version__
    except (ModuleNotFoundError, AttributeError):
        pass

    try:
        return ep.dist.metadata["Version"]
    except Exception:
        pass

    return "unknown"


class Command(BaseCommand):
    help = "List all installed Ophix plugins (ophix.plugins entry point group)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--details",
            action="store_true",
            help="Show pip package name, module, and version for each plugin.",
        )

    def _base_row(self):
        """Return the (name, package, module, version) row for ophix-server-base itself."""
        try:
            meta = dist_metadata("ophix-server-base")
            pip_name = meta["Name"]
        except Exception:
            pip_name = "ophix-server-base"
        version = _get_plugin_version("ophix", ep=None)
        if version == "unknown":
            try:
                version = dist_metadata("ophix-server-base")["Version"]
            except Exception:
                pass
        return ("ophix-server-base", pip_name, "ophix", version)

    def handle(self, *args, **options):
        details = options["details"]

        discovered = sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda ep: ep.name)

        if not details:
            self.stdout.write("ophix-server-base")
            for ep in discovered:
                self.stdout.write(ep.name)
            return

        # Detailed output — collect rows then format as a table.
        rows = [self._base_row()]
        for ep in discovered:
            module_name = ep.value
            pip_name = ep.dist.metadata["Name"] if ep.dist else "—"
            version = _get_plugin_version(module_name, ep)
            rows.append((ep.name, pip_name, module_name, version))

        # Column widths.
        w_name    = max(len("Plugin"),    max(len(r[0]) for r in rows))
        w_package = max(len("Package"),   max(len(r[1]) for r in rows))
        w_module  = max(len("Module"),    max(len(r[2]) for r in rows))
        w_version = max(len("Version"),   max(len(r[3]) for r in rows))

        header = (
            f"{'Plugin':<{w_name}}  "
            f"{'Package':<{w_package}}  "
            f"{'Module':<{w_module}}  "
            f"{'Version':<{w_version}}"
        )
        divider = "  ".join([
            "-" * w_name,
            "-" * w_package,
            "-" * w_module,
            "-" * w_version,
        ])

        self.stdout.write(header)
        self.stdout.write(divider)
        for name, package, module, version in rows:
            self.stdout.write(
                f"{name:<{w_name}}  "
                f"{package:<{w_package}}  "
                f"{module:<{w_module}}  "
                f"{version:<{w_version}}"
            )
