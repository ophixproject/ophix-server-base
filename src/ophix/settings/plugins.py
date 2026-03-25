"""
ophix.settings.plugins
~~~~~~~~~~~~~~~~~~~~~~
Discovers installed Ophix plugins via the ``ophix.plugins`` entry point
group and folds them into INSTALLED_APPS.

Each plugin package declares itself in its pyproject.toml::

    [project.entry-points."ophix.plugins"]
    my_plugin = "my_plugin_module"

On load this module:

1. Iterates all ``ophix.plugins`` entry points.
2. Skips any whose module name appears in OPHIX_DISABLE (comma-separated
   env var).
3. Appends the module name to INSTALLED_APPS if not already present.
4. Loads the plugin's settings defaults from
   ``<module>.settings`` (if it exists) without overwriting values
   already set by base.py or the environment.
5. Collects URL module references for ophix.urls.plugins to include.

This module mutates the globals() of its caller (settings/__init__.py)
so it must be called via ``plugins.apply(globals())`` rather than
imported directly.
"""

import importlib
import importlib.util
import logging
from importlib.metadata import entry_points

logger = logging.getLogger(__name__)

# Entry point group all Ophix plugins must register under.
ENTRY_POINT_GROUP = "ophix.plugins"


def _load_plugin_settings(module_name: str, target: dict) -> None:
    """
    Import ``<module_name>.settings`` and copy any settings it declares
    into *target*, without overwriting keys already present.

    Plugin settings modules should only define defaults — they must not
    unconditionally override base settings.
    """
    settings_module = f"{module_name}.settings"
    try:
        mod = importlib.import_module(settings_module)
    except ModuleNotFoundError:
        return  # Plugin has no settings module — perfectly fine.

    for key, value in vars(mod).items():
        if key.isupper() and key not in target:
            target[key] = value
            logger.debug("Plugin %s contributed setting %s", module_name, key)


def apply(target: dict) -> None:
    """
    Discover plugins and mutate *target* (the settings module globals).

    Called once from settings/__init__.py::

        from ophix.settings import plugins
        plugins.apply(globals())
    """
    import os

    disabled = {
        name.strip()
        for name in os.getenv("OPHIX_DISABLE", "").split(",")
        if name.strip()
    }

    if disabled:
        logger.info("Ophix plugins disabled via OPHIX_DISABLE: %s", disabled)

    installed_apps: list = target.setdefault("INSTALLED_APPS", [])

    # Collect URL contributors for ophix.urls.plugins
    plugin_url_modules: list[str] = []

    discovered = entry_points(group=ENTRY_POINT_GROUP)

    for ep in discovered:
        module_name = ep.value

        if module_name in disabled:
            logger.info("Skipping disabled plugin: %s", module_name)
            continue

        # Verify the module is actually importable before registering it.
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            logger.warning(
                "Plugin '%s' declared entry point '%s' but module is not importable — skipping.",
                ep.name,
                module_name,
            )
            continue

        if module_name not in installed_apps:
            installed_apps.append(module_name)
            logger.debug("Registered plugin app: %s", module_name)

        # Load plugin-level settings defaults (non-destructive).
        _load_plugin_settings(module_name, target)

        # Check whether the plugin contributes URL patterns.
        urls_module = f"{module_name}.urls"
        if importlib.util.find_spec(urls_module) is not None:
            plugin_url_modules.append(urls_module)
            logger.debug("Plugin %s contributes URLs from %s", module_name, urls_module)

    # Make the collected URL modules available for ophix.urls.plugins.
    target["OPHIX_PLUGIN_URL_MODULES"] = plugin_url_modules
