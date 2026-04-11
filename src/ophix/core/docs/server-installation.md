---
title: Server Installation
slug: server-installation
order: 1
section: Getting Started
---

An Ophix server is a Django application composed of two pip packages: `ophix-server-base`, which provides the core authentication, host/client management, and admin UI, and a domain plugin (e.g. `ophix-creds`, `ophix-confs`) that adds the specific functionality you need.

Both are installed in the same virtual environment.

---

## Prerequisites

- Python 3.10 or later
- MariaDB (with a database and user pre-created)
- A virtual environment tool (`python -m venv`)

---

## 1. Create the server directory and virtual environment

```bash
mkdir myserver && cd myserver
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows
```

---

## 2. Install the packages

Install `ophix-server-base` and one or more domain plugins:

```bash
pip install ophix-server-base
pip install ophix-creds           # credential domain
pip install ophix-confs           # configuration domain
```

Optional plugins:

```bash
pip install ophix-docs            # inline documentation
pip install ophix-codemirror      # code editor widgets
pip install ophix-theme-tools     # theme management commands
pip install ophix-theme-imago     # Imago branding theme
```

---

## 3. Configure the environment

Copy the sample environment file from the server-base package and edit it:

```bash
cp venv/lib/python3.*/site-packages/ophix/core/../../../sample.env .env
```

Or create `.env` directly in your server directory. Minimum required settings:

```ini
SERVER_NAME=My Ophix Server
DEBUG=false
ALLOWED_HOSTS=your.server.hostname,localhost

DB_NAME=ophix_db
DB_USER=ophixuser
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306

INSTALL_DIR=/path/to/myserver

LANGUAGE_CODE=en-au
TIME_ZONE=Australia/Melbourne
```

For development, additionally set:

```ini
DEBUG=true
AUTH_LEAK_INFO=true
```

`DJANGO_SECRET_KEY` is generated automatically on first run and written back to `.env`. You do not need to set it manually.

---

## 4. Create the database

```sql
CREATE DATABASE ophix_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL ON ophix_db.* TO 'ophixuser'@'localhost' IDENTIFIED BY 'yourpassword';
```

---

## 5. Run migrations

The `ophix-manage` command is the Django management entry point, installed by `ophix-server-base`:

```bash
ophix-manage migrate
```

This runs migrations for the base app and all installed domain plugins.

---

## 6. Create a superuser

```bash
ophix-manage createsuperuser
```

---

## 7. Start the server

For development:

```bash
ophix-manage runserver
```

The admin UI is available at `http://localhost:8000/admin/`.

For production, serve via gunicorn or uwsgi behind a reverse proxy (nginx recommended). See the deployment notes below.

---

## Production notes

- Set `DEBUG=false` and `AUTH_LEAK_INFO=false` in `.env`
- Set `ALLOWED_HOSTS` to your server's hostname
- Run `ophix-manage collectstatic` and serve `/static/` from nginx
- If behind a reverse proxy, the proxy **must** strip and re-set `X-Forwarded-For` — Ophix uses the source IP as part of client authentication. A misconfigured proxy allows IP spoofing.

---

## Registering clients

Once the server is running:

1. Go to **Admin → Hosts** and create a Host entry for the IP address of each machine that will run a client.
2. Clients register themselves on first run using the `quickstart` command — see [Client Quickstart](client-quickstart).

You do not need to pre-create Client records. Registration is handled by the client.

---

## Server settings

All settings are controlled via `.env`. Run `ophix-manage generate_deploy_config --env` to generate an annotated sample with all variables and their descriptions.

### Identity and security

| Variable | Default | Description |
| --- | --- | --- |
| `SERVER_NAME` | `Ophix Server` | Human-readable label shown in the admin header and footer |
| `SERVER_VERSION` | _(blank)_ | Version string set by release tooling; shown in the footer if `DISPLAY_VERSION_FOOTER=True` |
| `DJANGO_SECRET_KEY` | _(auto)_ | Auto-generated on first run and saved to `.env`. Do not set manually. |
| `DEBUG` | `False` | Enable Django debug mode. **Never True in production.** |
| `ALLOWED_HOSTS` | `*` | Comma-separated hostnames/IPs the server responds to. Tighten before going to production. |
| `AUTH_LEAK_INFO` | `False` | Include error detail in API responses. Set `True` during development only — `False` prevents auth failure fingerprinting in production. |

### Paths

| Variable | Default | Description |
| --- | --- | --- |
| `INSTALL_DIR` | `/home/websites/ophix` | Root directory for runtime data: logs, media, socket, SSL certs. Must be writable by the service user. |
| `DJANGO_MEDIA_ROOT` | `INSTALL_DIR/media` | Override the media files root if needed. |

### Database

| Variable | Default | Description |
| --- | --- | --- |
| `DB_NAME` | `ophix_db` | MariaDB database name |
| `DB_USER` | `ophixuser` | MariaDB user |
| `DB_PASSWORD` | _(blank)_ | MariaDB password |
| `DB_HOST` | `localhost` | MariaDB host |
| `DB_PORT` | `3306` | MariaDB port |

Use `ophix-manage configure_database` for interactive setup with a live connection test.

### Localisation

| Variable | Default | Description |
| --- | --- | --- |
| `LANGUAGE_CODE` | `en-au` | Django language code |
| `TIME_ZONE` | `UTC` | Server timezone (used for admin display and timestamps) |

### Admin UI visibility

These flags control which models appear in the Django admin navigation. All default to `False` (hidden). Enable in `.env` as required.

| Variable | Default | Description |
| --- | --- | --- |
| `SHOW_ACCESS_LOGS` | `False` | Show the Access Logs model — audit trail of client artifact access |
| `SHOW_THEME_MODEL` | `False` | Show the Django admin Themes model (django-admin-interface branding) |
| `SHOW_AUTH_MODELS` | `False` | Show Django's built-in Users and Groups models |
| `SHOW_CLIENT_ARTIFACT_MODEL` | `False` | Show the raw client-artifact join model (useful for debugging) |
| `DISPLAY_VERSION_FOOTER` | `False` | Show the server version string in the admin footer |
| `DISPLAY_COPYRIGHT` | `False` | Show the Ophix copyright line in the admin footer |

### API behaviour

| Variable | Default | Description |
| --- | --- | --- |
| `MINIMUM_TOKEN_ROTATE_TIME` | `3600` | Minimum seconds between token rotations. Prevents rotation abuse. Default is 1 hour. |
| `ENABLE_ARTIFACT_DELETE` | `False` | Allow clients to delete artifacts they own. Disabled by default — enable only if client-driven deletion is required. |

### Audit logging

| Variable | Default | Description |
| --- | --- | --- |
| `AUDIT_BATCH_SIZE` | `50` | Number of access events to accumulate before writing a batch to the database |
| `AUDIT_FLUSH_INTERVAL` | `5` | Maximum seconds to hold a partial batch before flushing. Ensures events are written promptly during low-traffic periods. |

See [Access Auditing](access-auditing) for the full audit log documentation, including how to prune old records.
