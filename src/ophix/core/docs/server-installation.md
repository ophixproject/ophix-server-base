---
title: Server Installation
slug: server-installation
order: 10
section: Getting Started
---

An Ophix server is a Django application composed of two pip packages:

- **`ophix-server-base`** — core authentication, host/client management, admin UI, and management commands
- **A domain plugin** (e.g. `ophix-creds`, `ophix-confs`, `ophix-certs`) — adds the specific functionality for this server instance

Both are installed in the same virtual environment. Each domain runs as its own server — a single instance runs one domain only.

---

## Prerequisites

- Python 3.10 or later
- MariaDB (recommended) or another supported database engine, with a database and user pre-created
- A virtual environment tool (`python -m venv`, or [`uv`](https://docs.astral.sh/uv/))
- nginx and systemd (for production deployments)

---

## 1. Create the server directory and virtual environment

```bash
mkdir credserver && cd credserver
python -m venv venv
source venv/bin/activate
```

Or, using [uv](https://docs.astral.sh/uv/):

```bash
mkdir credserver && cd credserver
uv venv
source .venv/bin/activate
```

uv doesn't install `pip` into the venv by default. Either replace `pip install` with `uv pip install` in the commands throughout this guide, or create the venv with `uv venv --seed` to have plain `pip` available. Ophix has no dependency on how the venv was created — see [Client Quickstart](client-quickstart) for the equivalent note on the client side.

---

## 2. Install packages

MariaDB support is built into `ophix-server-base` — no extra required. Install the domain plugin (`ophix-server-base` is pulled in automatically as a dependency):

```bash
pip install ophix-creds        # or ophix-confs, ophix-certs, etc.
```

**Other database engines** require a driver plugin in addition to the domain plugin:

```bash
pip install ophix-dbengine-postgres     # PostgreSQL
pip install ophix-dbengine-mssql        # SQL Server (also requires ODBC Driver 17/18)
pip install ophix-dbengine-cockroachdb  # CockroachDB
```

**Optional plugins** (install as needed):

```bash
pip install ophix-docs             # inline markdown documentation in admin
pip install ophix-theme-midnight   # custom branding theme (optional)
pip install ophix-codemirror       # code editor widgets (used by ophix-confs)
pip install ophix-auth-oidc        # OpenID Connect / Azure AD SSO
pip install ophix-auth-ldap        # Active Directory / LDAP authentication
pip install venv-cmds              # lists venv commands and checks for updates
```

---

## 3. Run the guided installer

The guided installer collects all required settings interactively and performs every setup step in sequence. Replace `credserver` with a short slug that identifies this server instance (e.g. `confserver`, `certserver`).

### Step 1 — Configure

```bash
ophix-manage configure_install credserver
```

This wizard collects:

- Install directory (runtime data: logs, SSL certs, socket)
- Server hostname (used in nginx config and TLS certificate validation)
- Service user and group
- TLS certificate and private key paths (validated against the hostname)
- Database connection details, with a live connection test before saving
- Superuser username, email, and password
- Theme to activate and admin title (if a theme package is installed)

Any installed domain plugin or extension that requires a generated key (such as `CRED_ENCRYPTION_KEY` for `ophix-creds` or `CA_KEY_ENCRYPTION_KEY` for `ophix-certs-ca`) is prompted for at the end of the wizard. For fresh installs the key is auto-generated; if you are rebuilding a venv against an existing database you must supply the original key instead.

The wizard writes two files:

- `.credserver.conf` — machine-readable configuration used by `run_install` (chmod 600)
- `.env` — Django environment settings with all values already patched in (chmod 600)

The wizard is **idempotent**: re-run it at any time to update individual settings. Existing values are loaded as defaults so you only need to change what has actually changed.

### Step 2 — Install

```bash
ophix-manage run_install credserver
```

This command reads `.credserver.conf` and performs all remaining setup steps:

1. Creates the `INSTALL_DIR` directory structure (`logs/`, `ssl/`, `run/`, etc.)
2. Copies TLS certificate and key into `ssl/certs/` and `ssl/private/`
3. Generates `credserver.nginx.conf`
4. Generates `credserver.service` (systemd unit for gunicorn)
5. Generates `credserver_sudo_install.sh` — the root script for step 3
6. Generates `credserver_sudo_uninstall.sh`
7. Writes any plugin-generated keys to `.env` (e.g. `CRED_ENCRYPTION_KEY`)
8. Runs `migrate`
9. Runs `collectstatic --noinput`
10. Creates or updates the superuser
11. Activates the selected theme and sets the admin title

Available flags: `--skip-migrate`, `--skip-collectstatic`, `--skip-superuser`

### Step 3 — System integration (as root)

```bash
sudo bash credserver_sudo_install.sh
```

This script:

- Sets ownership and permissions on `INSTALL_DIR`
- Installs `credserver.nginx.conf` into `/etc/nginx/sites-available/` and enables it
- Installs `credserver.service` into `/etc/systemd/system/`
- Enables and starts the service

After this step, the server is running and the admin UI is available at `https://your.hostname/admin/`.

---

## Upgrading

For most upgrades no reconfiguration is required — just upgrade the packages, run `migrate` and `collectstatic`, and restart the service:

```bash
pip install --upgrade ophix-server-base ophix-creds   # and any other installed packages
ophix-manage migrate
ophix-manage collectstatic --noinput
sudo systemctl restart credserver
```

**If the upgrade adds new `.env` settings**, use `generate_config --append` to add them without touching existing values:

```bash
ophix-manage generate_config --append
# Review any new keys added to .env and set non-default values if needed
ophix-manage migrate
ophix-manage collectstatic --noinput
sudo systemctl restart credserver
```

`--append` discovers all installed plugin env fragments and adds only the keys not already present in `.env`. Existing values and manual edits are never modified.

**If you need to change configuration** (new hostname, replace a TLS certificate, change database):

```bash
ophix-manage configure_install credserver    # re-prompts with existing values as defaults
ophix-manage run_install credserver --skip-superuser
sudo bash credserver_sudo_install.sh
```

Avoid re-running `configure_install` for routine upgrades — it rewrites `.env` from scratch, which would discard any manual edits not captured in `.credserver.conf`.

---

## Development setup

For a local development environment, skip the guided installer and set `.env` manually:

```ini
DEBUG=True
AUTH_LEAK_INFO=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=ophix_db
DB_USER=ophixuser
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306

INSTALL_DIR=/path/to/credserver
```

Then:

```bash
ophix-manage migrate
ophix-manage createsuperuser
ophix-manage runserver
```

The admin UI is available at `http://localhost:8000/admin/`.

`DJANGO_SECRET_KEY` is generated automatically on first run and written back to `.env`.

---

## Manual / legacy installation

The guided installer is recommended for all new deployments. If you prefer to manage each step yourself, the following commands are available individually:

| Command | Purpose |
| --- | --- |
| `generate_config --all` | Generate `.env.sample`, nginx config, and systemd service file |
| `generate_config --append` | Add new plugin env keys to an existing `.env` without modifying existing values |
| `configure_database` | Interactive database credentials setup with live connection test |
| `configure_install` | Create `INSTALL_DIR` subdirectory structure |
| `migrate` | Apply database migrations |
| `collectstatic --noinput` | Collect static files |
| `createsuperuser` | Create an admin user interactively |
| `run_uninstall <slug>` | Regenerate the sudo uninstall script |

Full legacy sequence: `generate_config --all` → `configure_database` → `configure_install` → place TLS files → deploy nginx and systemd files → `migrate` → `collectstatic` → `createsuperuser` → `systemctl start`.

---

## Production notes

- `.env` and `.credserver.conf` both contain secrets — they are written with `chmod 600` by the installer. Verify this after any manual edits.
- Set `DEBUG=False` and `AUTH_LEAK_INFO=False` in production (both are `False` by default).
- If deployed behind a load balancer, the LB **must** strip and re-set `X-Forwarded-For` before requests reach nginx. Ophix uses the source IP as part of client authentication — a misconfigured proxy allows IP spoofing.
- Back up `CRED_ENCRYPTION_KEY` and `CA_KEY_ENCRYPTION_KEY` (if applicable) to secure offline storage. These keys are not recoverable if lost, and losing them means losing access to all encrypted data.

---

## Adding a plugin to an existing deployment

```bash
pip install ophix-<plugin>
ophix-manage generate_config --append
# Edit .env to set any new values if required
ophix-manage migrate
ophix-manage collectstatic --noinput
sudo systemctl restart credserver
```

---

## Registering clients

Once the server is running:

1. Go to **Admin → Hosts** and create a Host entry for the IP address of each machine that will run a client.
2. Clients register themselves on first run using the `quickstart` command — see [Client Quickstart](client-quickstart).

You do not need to pre-create Client records. Registration is handled by the client.

---

## Server settings reference

All settings are controlled via `.env`. Run `ophix-manage generate_config --env` to generate an annotated sample with all variables.

### Identity and security

| Variable | Default | Description |
| --- | --- | --- |
| `SERVER_NAME` | _(domain default)_ | Short name for this server instance. The domain plugin supplies a default (`credserver`, `confserver`, `certserver`, etc.). Override to customise for a specific deployment. |
| `SERVER_VERSION` | _(blank)_ | Version string auto-populated from the installed domain plugin. Updated automatically by `generate_config --append` after an upgrade. |
| `DJANGO_SECRET_KEY` | _(auto)_ | Auto-generated on first run and saved to `.env`. Do not set manually. |
| `DEBUG` | `False` | Enable Django debug mode. **Never `True` in production.** |
| `ALLOWED_HOSTS` | `*` | Comma-separated hostnames/IPs this server responds to. Tighten before production. |
| `AUTH_LEAK_INFO` | `False` | Include error detail in API responses. `True` during development only — `False` prevents auth failure fingerprinting in production. |

### Paths

| Variable | Default | Description |
| --- | --- | --- |
| `INSTALL_DIR` | _(current directory)_ | Root directory for runtime data: logs, media, socket, SSL certs. Must be writable by the service user. |
| `DJANGO_MEDIA_ROOT` | `INSTALL_DIR/media` | Override the media files root if needed. |

### Database

| Variable | Default | Description |
| --- | --- | --- |
| `DB_ENGINE` | `mariadb` | Database backend. Valid values: `mariadb`, `mysql`, `postgres`, `sqlserver`, `cockroachdb`. Install the matching driver plugin for non-MariaDB engines. |
| `DB_NAME` | `ophix_db` | Database name |
| `DB_USER` | `ophixuser` | Database user |
| `DB_PASSWORD` | _(blank)_ | Database password |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `3306` | Database port. Default `3306` for MariaDB/MySQL; `5432` for PostgreSQL; `1433` for SQL Server; `26257` for CockroachDB. |
| `DB_SSL_CA` | _(blank)_ | CA certificate path for database TLS. Setting this enables TLS. |
| `DB_SSL_CERT` | _(blank)_ | Client certificate path. Only required for mutual TLS. |
| `DB_SSL_KEY` | _(blank)_ | Client private key path. Required only when `DB_SSL_CERT` is set. |

### Localisation

| Variable | Default | Description |
| --- | --- | --- |
| `LANGUAGE_CODE` | `en-au` | Django language code |
| `TIME_ZONE` | `UTC` | Server timezone |

### Admin UI visibility

All default to `False`. Enable in `.env` as needed.

| Variable | Description |
| --- | --- |
| `SHOW_ACCESS_LOGS` | Show the Access Logs model — audit trail of client artifact access |
| `SHOW_THEME_MODEL` | Show the Django admin Themes model |
| `SHOW_AUTH_MODELS` | Show Django's built-in Users and Groups models |
| `SHOW_CLIENT_ARTIFACT_MODEL` | Show the raw client-artifact join model (useful for debugging) |
| `DISPLAY_VERSION_FOOTER` | Show `SERVER_NAME-SERVER_VERSION` in the admin footer |
| `DISPLAY_COPYRIGHT` | Show the Ophix copyright line in the admin footer |

### API behaviour

| Variable | Default | Description |
| --- | --- | --- |
| `MINIMUM_TOKEN_ROTATE_TIME` | `3600` | Minimum seconds between token rotations |
| `ENABLE_ARTIFACT_DELETE` | `False` | Allow clients to delete their own artifacts |

### Audit logging

| Variable | Default | Description |
| --- | --- | --- |
| `AUDIT_BATCH_SIZE` | `50` | Access events to accumulate before a batch database write |
| `AUDIT_FLUSH_INTERVAL` | `5` | Maximum seconds to hold a partial batch before flushing |

Access log timestamps are always stored in UTC regardless of the `TIME_ZONE` setting.

**MariaDB / MySQL — timezone tables required for non-UTC `TIME_ZONE`**

When `TIME_ZONE=UTC` (the default), the Access Logs admin view works out of the box. If you set a non-UTC `TIME_ZONE` (e.g. `Australia/Sydney`), the admin date filtering and date hierarchy rely on MariaDB's `CONVERT_TZ()` function, which requires the timezone tables to be populated. Without them you will see:

```text
ValueError: Database returned an invalid datetime value.
Are time zone definitions for your database installed?
```

To install the timezone tables (one-time, per MariaDB/MySQL instance):

```bash
mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -h 127.0.0.1 -u root -p mysql
sudo systemctl restart mariadb
```

`-h 127.0.0.1` connects explicitly to localhost (adjust if your MariaDB/MySQL is on a different host). `-u root` uses the root database user. `-p` prompts for the password interactively. The target database is `mysql` — this is the system database where timezone tables live and is not the Ophix application database.

PostgreSQL, SQL Server, Oracle, and CockroachDB are not affected — they carry their own timezone data.

See [Access Auditing](access-auditing) for the full audit log documentation.

### Authentication plugins

SSO and LDAP are optional plugins, not part of `ophix-server-base`. Install the plugin and re-run `generate_config --append` to add the relevant settings block to `.env`.

```bash
pip install ophix-auth-oidc    # OpenID Connect / Azure AD
pip install ophix-auth-ldap    # Active Directory / LDAP
ophix-manage generate_config --append
```

Each plugin activates when its trigger variable is set in `.env`: `OIDC_RP_CLIENT_ID` for OIDC, `LDAP_SERVER_URI` for LDAP. Both can be active simultaneously.
