# ophix-server-base

Base Django project package for **Ophix Project Servers** (OPS).

Provides the shared infrastructure that every OPS server is built on:
Host/Client models, token + IP authentication, standard API endpoints
(register, CA cert download, client self-management), settings module
with plugin auto-discovery, and URL assembly.

---

## Installation

```bash
pip install ophix-server-base
```

Install domain plugins alongside it:

```bash
pip install ophix-server-base ophix-creds ophix-docs ophix-theme-tools
```

---

## Configuration

```bash
cp sample.env .env
# Edit .env for your deployment
```

Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `SERVER_NAME` | `Ophix Server` | Human-readable name shown in admin |
| `DB_NAME` | `ophix_db` | MariaDB database name |
| `INSTALL_DIR` | `/home/websites/ophix` | Root for persistent runtime data |
| `CA_CERT_FILE` | — | Path to internal CA cert (served unauthenticated) |
| `AUTH_LEAK_INFO` | `false` | Verbose API errors (development only) |
| `OPHIX_DISABLE` | — | Comma-separated plugin modules to suppress |

---

## Django management

```bash
# Using the installed entry point
ophix-manage migrate
ophix-manage collectstatic
ophix-manage createsuperuser

# Or via Python
python -m ophix.manage migrate
```

Always set `DJANGO_SETTINGS_MODULE=ophix.settings` (the default).

---

## Plugin system

Any pip-installable package that registers under the `ophix.plugins`
entry point group is automatically added to `INSTALLED_APPS` and its
URLs are included.

```toml
# In your plugin's pyproject.toml:
[project.entry-points."ophix.plugins"]
my_plugin = "my_plugin_module"
```

To suppress an installed plugin without uninstalling it:

```bash
OPHIX_DISABLE=my_plugin_module
```

---

## Standard API endpoints

Every OPS server exposes these regardless of installed plugins:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/server/ca-cert/` | None | Download internal CA cert |
| `POST` | `/api/register/` | None | Register a new client |
| `GET` | `/api/client/self/` | Token | Client self-inspection |
| `PATCH` | `/api/client/self/update/` | Token | Update venv/deployment info |
| `POST` | `/api/client/self/rotate-token/` | Token | Rotate API token |

---

## Authentication

All authenticated endpoints require:

```
Authorization: Token <64-char hex token>
```

Requests are also validated against the client's registered Host IP.
Both conditions must pass. See `ophix.core.auth.ClientTokenAuthentication`.
