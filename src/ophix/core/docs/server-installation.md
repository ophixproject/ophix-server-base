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
- MariaDB, MySQL, or PostgreSQL (with a database and user pre-created)
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

Install `ophix-server-base` with the database driver for your engine, and one or more domain plugins:

```bash
pip install ophix-server-base[mariadb]  # MariaDB (recommended default)
pip install ophix-server-base[mysql]    # MySQL
pip install ophix-server-base[postgres] # PostgreSQL
```

To enable SSO, add the `sso` extra (can be combined with the DB extra):

```bash
pip install "ophix-server-base[mariadb,sso]"
```

> **Upgrading an existing MariaDB installation:** `DB_ENGINE` defaults to `mariadb` if not set, so no `.env` change is required. `mysqlclient` is no longer a hard dependency — it is now the `[mariadb]` extra — but pip does not remove already-installed packages, so existing venvs continue to work without any action.

```bash
pip install ophix-creds                 # credential domain
pip install ophix-confs                 # configuration domain
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
DEBUG=false
ALLOWED_HOSTS=your.server.hostname,localhost

# DB_ENGINE defaults to mariadb. Set to postgres for PostgreSQL.
# DB_ENGINE=postgres

DB_NAME=ophix_db
DB_USER=ophixuser
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306    # use 5432 for PostgreSQL

INSTALL_DIR=/path/to/myserver

LANGUAGE_CODE=en-au
TIME_ZONE=Australia/Melbourne
```

`SERVER_NAME` defaults to the domain plugin's built-in value (`certserver`, `credserver`, `confserver`, etc.) and does not need to be set unless you want to customise it for a specific deployment.

For development, additionally set:

```ini
DEBUG=true
AUTH_LEAK_INFO=true
```

`DJANGO_SECRET_KEY` is generated automatically on first run and written back to `.env`. You do not need to set it manually.

---

## 4. Create the database

**MariaDB / MySQL:**

```sql
CREATE DATABASE ophix_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL ON ophix_db.* TO 'ophixuser'@'localhost' IDENTIFIED BY 'yourpassword';
```

**PostgreSQL:**

```sql
CREATE DATABASE ophix_db;
CREATE USER ophixuser WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE ophix_db TO ophixuser;
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
| `SERVER_NAME` | _(domain default)_ | Short name for this server instance. The installed domain plugin supplies a default (`certserver`, `credserver`, `confserver`, etc.). Override in `.env` to customise for a specific deployment. When `DISPLAY_VERSION_FOOTER=True`, the footer displays `SERVER_NAME-SERVER_VERSION`. |
| `SERVER_VERSION` | _(blank)_ | Version string auto-populated from the installed domain plugin by `generate_deploy_config`. Re-run `generate_deploy_config --append` after upgrading — it detects the new version and updates this value automatically. Shown in the footer as `SERVER_NAME-SERVER_VERSION` when `DISPLAY_VERSION_FOOTER=True`. |
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
| `DB_ENGINE` | `mariadb` | Database backend. Valid values: `mariadb`, `mysql`, `postgres`. Install the matching driver extra: `ophix-server-base[mariadb]`, `[mysql]`, or `[postgres]`. |
| `DB_NAME` | `ophix_db` | Database name |
| `DB_USER` | `ophixuser` | Database user |
| `DB_PASSWORD` | _(blank)_ | Database password |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `3306` | Database port. Default is `3306` for MariaDB/MySQL; use `5432` for PostgreSQL. |
| `DB_SSL_CA` | _(blank)_ | Path to the CA certificate used to verify the database server. Setting this enables TLS. For PostgreSQL, `sslmode=verify-ca` is used when this is set. Leave blank for an unencrypted connection. |
| `DB_SSL_CERT` | _(blank)_ | Path to the client certificate. Only required for mutual TLS (client certificate authentication). |
| `DB_SSL_KEY` | _(blank)_ | Path to the client private key. Required only when `DB_SSL_CERT` is set. |

Use `ophix-manage configure_database` for interactive setup with a live connection test. The command prompts for the engine first and adjusts port defaults accordingly.

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
| `DISPLAY_VERSION_FOOTER` | `False` | Show `SERVER_NAME-SERVER_VERSION` in the admin footer (e.g. `certserver-2026.04.12.01`) |
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

### SSO — OpenID Connect

SSO requires the `[sso]` extra (`pip install "ophix-server-base[mariadb,sso]"`). It is activated when `OIDC_RP_CLIENT_ID` is set in `.env`. Without that setting, the standard Django username/password login is used and the `[sso]` package does not need to be installed.

When SSO is active, a **Sign in with SSO** button appears on the admin login page alongside the standard username/password form. Both methods remain available — local superuser accounts still work for emergency access.

#### Azure AD setup

1. Register an application in Azure AD → **App registrations → New registration**.
2. Set the redirect URI to `https://yourserver/oidc/callback/` (type: Web).
3. Under **Token configuration**, add the **groups** optional claim to the ID token.
4. Note the **Application (client) ID** and **Directory (tenant) ID**.
5. Create a client secret under **Certificates & secrets**.

```ini
OIDC_RP_CLIENT_ID=<application client id>
OIDC_RP_CLIENT_SECRET=<client secret value>
OIDC_AZURE_TENANT_ID=<directory tenant id>
```

Setting `OIDC_AZURE_TENANT_ID` auto-derives all four OIDC endpoint URLs. For other providers (Keycloak, Okta, etc.), set `OIDC_OP_AUTHORIZATION_ENDPOINT`, `OIDC_OP_TOKEN_ENDPOINT`, `OIDC_OP_USER_ENDPOINT`, and `OIDC_OP_JWKS_ENDPOINT` directly.

#### Group-based permissions

By default, all users who successfully authenticate via SSO are granted `is_staff = True` (admin access). To restrict access:

```ini
OIDC_STAFF_GROUP_ID=<object ID of your staff group>
OIDC_SUPERUSER_GROUP_ID=<object ID of your superuser group>
```

Set the value to the group's object ID (GUID) in Azure AD. Users not in either group are denied admin access. A user in the superuser group gets both `is_staff` and `is_superuser`.

| Variable | Default | Description |
| --- | --- | --- |
| `OIDC_RP_CLIENT_ID` | _(blank)_ | Application (client) ID from your IdP. Setting this activates SSO. |
| `OIDC_RP_CLIENT_SECRET` | _(blank)_ | Client secret for the application registration. |
| `OIDC_AZURE_TENANT_ID` | _(blank)_ | Azure AD tenant ID. Auto-derives all four OIDC endpoint URLs when set. |
| `OIDC_RP_SIGN_ALGO` | `RS256` | Token signing algorithm. Change if required by your IdP. |
| `OIDC_RP_SCOPES` | `openid profile email` | Scopes to request. No extra scope needed for Azure AD group claims. |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | _(blank)_ | Authorization endpoint URL (derived automatically for Azure AD). |
| `OIDC_OP_TOKEN_ENDPOINT` | _(blank)_ | Token endpoint URL (derived automatically for Azure AD). |
| `OIDC_OP_USER_ENDPOINT` | _(blank)_ | Userinfo endpoint URL (derived automatically for Azure AD). |
| `OIDC_OP_JWKS_ENDPOINT` | _(blank)_ | JWKS endpoint URL (derived automatically for Azure AD). |
| `OIDC_STAFF_GROUP_ID` | _(blank)_ | IdP group ID whose members receive `is_staff`. If blank, all SSO users get staff access. |
| `OIDC_SUPERUSER_GROUP_ID` | _(blank)_ | IdP group ID whose members receive `is_staff` + `is_superuser`. |
| `OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS` | `900` | How often (seconds) the session middleware re-validates the OIDC token. |
