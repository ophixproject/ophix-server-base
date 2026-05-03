# ADR-002: Plugin discovery via entry points

**Date:** 2026-03-01 (approx)
**Status:** Accepted

## Context

Ophix servers are composed of `ophix-server-base` plus one domain plugin plus optional extension plugins. The base package needs to discover and load whatever plugins are installed without being modified each time a new plugin is added.

Options considered:

1. **Explicit `INSTALLED_APPS` list in `.env`** — operator lists plugins manually. Simple, but error-prone and requires documentation to stay in sync.
2. **Convention-based discovery** — scan for packages named `ophix-*`. Fragile, catches unintended packages.
3. **`importlib.metadata` entry points** — plugins declare themselves in `pyproject.toml` under a group; the base discovers them at runtime.

## Decision

Plugins declare themselves under the `ophix.plugins` entry point group:

```toml
[project.entry-points."ophix.plugins"]
my_plugin = "my_plugin_module"
```

`ophix-server-base` discovers all registered entries via `importlib.metadata.entry_points(group="ophix.plugins")`, adds the module to `INSTALLED_APPS`, loads settings non-destructively (defaults only, cannot override base settings), and includes the plugin's URL module.

Plugins can be suppressed without uninstalling via `OPHIX_DISABLE=module_name` in `.env`.

A special `INSTALLED_APPS` key in a plugin's `settings.py` extends (not replaces) the app list, allowing plugins to declare third-party Django app dependencies (e.g. `django_object_actions`). Deduplication is handled automatically.

## Consequences

- Adding a plugin is `pip install` only — no configuration changes needed
- `ophix-manage list_ophix_plugins` gives a full inventory of what is installed
- Plugins are truly composable; the base package has no knowledge of any specific plugin
- A misconfigured plugin (bad entry point, import error) fails at startup with a clear traceback rather than silently being skipped
- Plugins cannot override base settings — intentional to prevent plugins from breaking the host server
