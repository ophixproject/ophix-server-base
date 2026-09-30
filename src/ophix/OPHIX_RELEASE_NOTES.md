# ophix-server-base Release Notes

## Unreleased

- Docs/copy fix, found on the same taskserver walkthrough: `configure_install`'s backup
  passphrase prompt said "Leave blank to skip encryption," which undersells what actually
  happens — leaving it blank doesn't produce an unencrypted backup of those targets, it skips
  backing them up **entirely** (confirmed by the very next line the wizard prints: "No passphrase
  set — .env file backup will be disabled", and later by "Targets requiring a passphrase
  excluded"). Reworded to state the real consequence directly, and explain why (secrets are never
  written to a backup unencrypted). `server-backup.md`'s equivalent line updated to match.

## 2026.09.30.02

- **Real fresh-install bug, found on the first live taskserver walkthrough**: `configure_install`,
  `configure_database`, and `generate_config` were all crashing with a raw Django traceback
  before ever prompting for anything, on a server with no `.env` yet. Django's `BaseCommand`
  runs its full system check suite before `handle()` starts for every management command by
  default — for the MySQL/MariaDB backend, even an unrelated model field check needs a real DB
  connection just to build its internal type map (`has_native_uuid_field` requires a live query
  to detect MariaDB vs MySQL), and that connection attempt used whatever fallback/blank settings
  happened to be in `os.environ`, which is never a real working account on a fresh box. All three
  commands now set `requires_system_checks = []` to skip this entirely — matching what
  `configure_database`'s own docstring already promised ("safe to run before the database schema
  exists") but Django's default behaviour was quietly breaking. `run_install` is unaffected and
  intentionally untouched — by the time it runs, `.env` already has real, tested credentials from
  `configure_install`, so the checks there are legitimate.

- **Second real bug from the same walkthrough**: `configure_install`'s new `[nginx]` section
  (added in `2026.09.29.01`) crashed with `configparser.NoSectionError: No section: 'nginx'` the
  moment the wizard tried to save the nginx config directory prompt. `_handle()` pre-creates every
  `.conf` section it's about to write to in one place — `for section in ("server", "tls",
  "database", "superuser", "admin", "backup")` — and `"nginx"` was simply never added to that
  tuple when the section was introduced. `conf.get(..., fallback=...)` tolerates a missing
  section silently, which is why the read side of the new prompts worked fine right up until the
  first `conf.set()` call. Fixed by adding `"nginx"` to the tuple. No partial `.conf` file is ever
  written on a crash like this — the file is only written once, at the very end of the wizard —
  so this required no cleanup on the affected test install, just a re-run.

## 2026.09.30.01

- Follow-up to the `mysqlclient` split below: `configure_database` and `configure_install` now
  base database engine selection on which `ophix-dbengine-*` plugins are actually installed,
  instead of always prompting for an engine and only discovering a missing driver later. With no
  dbengine plugin installed at all, both abort immediately with install instructions for every
  engine — before any host/port/credential/TLS prompt, not just before the live test. With
  exactly one plugin installed (the common case — e.g. just `ophix-dbengine-mariadb`), it's
  auto-selected with no prompt at all, unless a *different* engine was already explicitly
  configured from a prior run, in which case it warns about the mismatch and asks rather than
  silently switching a working config. With two or more installed, the engine prompt still
  appears but only offers the installed ones as valid choices.

## 2026.09.29.01

- `configure_install` now prompts for the nginx config directory and enabled directory, instead of
  hardcoding the Debian/Ubuntu `sites-available`/`sites-enabled` split. Defaults unchanged
  (`/etc/nginx/sites-available` + `/etc/nginx/sites-enabled`), so existing behaviour is preserved
  for anyone who just presses Enter through the new prompts. Leaving the enabled directory blank
  (e.g. pointed at `/etc/nginx/conf.d` for RHEL/Fedora-family distros) skips the symlink step
  entirely in the generated `<slug>_sudo_install.sh`/`<slug>_sudo_uninstall.sh` — those distros
  load `*.conf` files directly from one directory with no separate enable step. Stored in the new
  `[nginx]` section of `.<slug>.conf`; existing `.conf` files without it fall back to the same
  Debian/Ubuntu defaults `run_install` always used. `server-installation.md` updated to document
  the new prompts and the RHEL-style layout.

- **Breaking (packaging only, not runtime): `mysqlclient` is no longer a hard dependency.**
  Every install using MariaDB/MySQL now needs `ophix-dbengine-mariadb` installed explicitly, same
  as every other engine already required. This removes the unwanted build-time cost (a
  C-extension with no reliable universal wheel) for anyone using a different engine — Postgres,
  SQL Server, Oracle, and CockroachDB installs no longer pull in a driver they never use. MariaDB
  stays the *recommended* default across every install doc, just no longer silently bundled.
  Already-deployed servers are unaffected — pip doesn't uninstall a dependency just because a
  newer release stops requiring it. README, `server-installation.md`, and every domain package's
  own install docs updated to include `ophix-dbengine-mariadb` in the recommended install line.

- `configure_database`'s live connection test now covers all six supported engines, not four.
  SQL Server (via `pyodbc`) and Oracle (via `oracledb`, thin mode) previously had no tester at
  all — the wizard explicitly skipped the live test for both and asked the operator to verify
  connectivity manually after writing `.env`. Both now get a real pre-flight check with the same
  graceful "driver not installed, run: pip install X" handling the MySQL/Postgres testers already
  had, plus pattern-matched guidance for the common failure cases (bad credentials, unknown
  database/service, driver not found, unreachable server).

## 2026.09.26.05

- i18n regression check: wrapped 12 previously-unwrapped user-facing strings across `auth.py`, `views.py`, `middleware.py`, `utils.py`, and `admin.py` (API error responses, read-only-mode message, Plugin Versions panel labels) in `gettext_lazy`/`gettext` — these files had never been brought into the earlier i18n pass at all, unlike `models.py`/`admin.py`'s field-level strings. Also fixed a shadowing bug in `favicon_view` where a throwaway `_` variable would have clobbered the new `gettext_lazy as _` import for the rest of the function (same footgun previously fixed in `check_updates.py`).

## 2026.09.26.04

- Verified real compatibility under Python 3.14 (not just added the classifier) as part of the taskserver-release-wave compatibility sweep, and added `Programming Language :: Python :: 3.14` to the package classifiers.

## 2026.09.26.03

- Fixed a real bug in the sqlserver DATABASES wiring: `DB_SQLSERVER_ENCRYPT`
  and `DB_SQLSERVER_TRUST_CERT` were passed as top-level `OPTIONS` dict keys,
  but the currently-resolved `mssql-django` (2.0.0) never reads them from
  there — `_build_connection_string()` only reads `dsn`/`extra_params`/
  `host_is_server`/`python_driver` from top-level `OPTIONS`. Both env vars
  were silently doing nothing regardless of what an operator set. Found via
  real testing (a fresh SQL Server instance's own self-signed cert was
  rejected even with `DB_SQLSERVER_TRUST_CERT=yes`). Fixed by passing both
  through `OPTIONS["extra_params"]` as a raw `Encrypt=...;TrustServerCertificate=...`
  string, the format this mssql-django version actually expects. Verified
  against a live SQL Server instance — migrate now succeeds with
  `DB_SQLSERVER_TRUST_CERT=yes` against a default self-signed cert.

## 2026.09.26.02

- Docs: restored `ophix-auth-oidc` to `server-installation.md`'s optional
  plugins list — it now has a real unit test suite (see `ophix-auth-oidc`'s
  own release notes) clearing the bar for an Alpha release. Oracle stays
  removed; its own confidence level hasn't changed.
- Docs: `server-installation.md`'s `ophix-codemirror` line only credited
  `ophix-confs` as a consumer — `ophix-creds` uses it too (`JSONCodeMirrorWidget`
  for `secret_json`), confirmed directly in `ophix-creds/admin.py`.

## 2026.09.26.01

- `configure_database`: fixed a real bug where selecting SQL Server, Oracle, or
  CockroachDB in the interactive wizard ran the live connection test using the
  MySQL tester regardless of engine — guaranteed to fail for all three (wrong
  wire protocol). CockroachDB now correctly reuses the Postgres tester (it's
  Postgres-wire-compatible); SQL Server and Oracle now skip the live test with
  a clear message instead of silently testing the wrong protocol. Default port
  suggestions also fixed for all engines (was only ever correct for
  postgres/mariadb).
- Docs: removed Oracle and OIDC from `server-installation.md`'s install
  commands and the `DB_ENGINE` valid-values list — Oracle has no TLS wiring
  and has never been verified even for plaintext connectivity; OIDC has no
  test-harness evidence at all. Both stay code-complete, just not advertised
  until each clears its own bar for release.
- `testing/db-engines/` (dev tooling, not shipped): added a SQL Server cell to
  the DB engine test harness, verifying its TLS-validates-against-OS-trust-store
  claim directly rather than by code inspection only. All 4 real scenarios
  pass — SQL Server now has the same empirical confidence as MariaDB/Postgres/
  CockroachDB.

## 2026.08.31.01

- Client change view: the "WARNING: Issuing a replacement token…" line now uses
  the theme's delete/danger colour (`--admin-interface-delete-button-background-color`)
  instead of the warning colour — this action is destructive (immediately locks
  out the existing client), which the delete colour communicates more accurately
  than the warning colour.

## 2026.08.30.03

- Changelist disabled/paused row styling reworked into two independent,
  non-overlapping treatments: disabled affects text only (italic row +
  disabled-coloured name link, `--admin-interface-disabled-color`, new in
  `ophix-admin-interface 2026.08.30.11`) and never touches the background — an
  enabled, unpaused row's background stays the standard alternating row
  stripe. Paused affects background only (the existing amber tint) and never
  touches text. A row that is both disabled and paused gets both treatments
  simultaneously, since neither rule ever sets the other's property — no
  priority/override logic needed. The previous version of this change
  (removing paused row's background) was a misreading of the ask; corrected
  before release. Both rules are declared in the single shared
  `tr:has(td.field-enabled ...)` / `tr:has(td.field-paused ...)` selectors in
  `custom.css`, so this applies globally to every changelist with an
  `enabled`/`paused` checkbox column — Hosts, Clients, Schedules, Scheduled
  Tasks, Credentials, Configurations, etc. — with no per-model changes needed.
  Also fixed a stale doc comment referencing
  `--ophix-paused-color`/`--ophix-disabled-color` custom properties that were
  never actually declared anywhere in the file.

- Plugin Versions "Release Notes" panel: fixed multi-line entries being truncated to
  just their first line. Release notes bullets that wrap across several lines in the
  source `OPHIX_RELEASE_NOTES.md` (continuation lines indented, with no leading `-`
  or `*` marker) were silently dropped by the parser — only the first line of each
  bullet ever reached the rendered panel. Continuation lines are now appended to the
  preceding bullet's text instead of being ignored.

## 2026.08.30.01

- Plugin Versions "Release Notes" panel: removed the per-version collapse toggle.
  Expanding the outer "RELEASE NOTES" section now shows every version's changes in
  one continuous list, with each version string still rendered as its own heading —
  no more clicking each version open individually to read it.
- Client change view: the "Issuing a replacement token will immediately lock out..."
  line under the "Issue a replacement token" button is now prefixed with "WARNING:"
  and rendered in the theme's warning colour (`--admin-interface-warning-color`,
  bold) instead of the muted body-quiet colour it inherited by default.

## 2026.08.12.01

- Django dependency split by `python_version` marker: `Django>=4.2,<6.0` on Python < 3.12,
  `Django>=4.2` (no upper bound) on Python >= 3.12. Django 6.0 itself requires Python 3.12+;
  this makes the "Python 3.10/3.11 + Django 6" combination structurally unreachable via pip's
  resolver instead of failing at runtime, while still allowing 3.10/3.11 hosts to run on
  Django 5.2. `requires-python` is unchanged (`>=3.10` remains the true floor).

## 2026.08.04.01

- `export_hosts`/`export_clients` gain a `--stable` flag: omits the `meta` block
  (`created_at`/`hostname`/`run_by`/`login_user`/`ssh_origin` — all run/machine-specific
  noise) and passes `sort_keys=True`, so re-exporting unchanged data produces byte-identical
  output. Written for `ophix-revisions` (git-backed continuous history — commits only when
  the export actually differs from what's already there), but usable standalone by anyone
  who wants reproducible exports. Normal (non-`--stable`) output is unchanged.
- `ophix.core` gains `get_revisions_targets()`, declaring its own `hosts`/`clients`/`env`
  targets for `ophix-revisions` (if installed) to discover at runtime. `ophix-revisions`
  holds no hardcoded catalog of domain packages — each package declares its own targets via
  this optional hook, so a brand-new domain becomes usable with `ophix-revisions` without any
  change needed in `ophix-revisions` itself.

## 2026.07.12.02

- `Client.api_token` renamed to `Client.token_hash`. The field has stored a SHA-256 hash
  (not a live credential) since the session-28 token-hashing work, but the field name never
  changed to reflect that — a hash and the original token look like similarly-shaped opaque
  hex strings, so anyone looking at a `client export` JSON file had no visual cue that the
  value is a hash. Plain column rename via migration `0004` (`RenameField` — `ALTER TABLE ...
  RENAME COLUMN`, existing values preserved, no data transformation). Fleet clients are
  unaffected — they never read this field, only ever send their plaintext token in the
  Authorization header. **Breaking change to the `export_clients`/`import_clients` JSON
  schema**: the `api_token` key is now `token_hash`; export payload `version` bumped to `2`.
  `import_clients` rejects older files with a clear error pointing at re-export rather than
  silently skipping every record. `ClientAdmin.api_token_display` renamed to
  `token_hash_display` to match.

## 2026.07.12.01

- Documented that `DB_SSL_CA`/`DB_SSL_CERT`/`DB_SSL_KEY` (`env.sample.j2`) only apply to
  `DB_ENGINE=mariadb/mysql`, `postgres`, and `cockroachdb`. They have no effect for
  `sqlserver` (TLS is on by default, validated against the OS certificate trust store —
  see the mssql plugin's own env fragment) or `oracle` (TLS is not currently supported by
  that engine plugin at all — enabling `DB_ORACLE_THICK_MODE` does not configure an Oracle
  Wallet or any other TLS parameter, it only switches the underlying client library).
  Found while scoping out a DB-engine TLS/plaintext testing matrix — no functional change,
  comments only (`env.sample.j2` and `settings/base.py`).

- `<slug>-update.sh` (`create_update_script`) now refuses to run as root — mirrors the
  existing root-required guard on `<slug>_sudo_install.sh`, but inverted. This script is
  designed to run entirely as the unprivileged service user; running it under `sudo` causes
  any `.env` rewrite mid-run (e.g. the `SERVER_VERSION` bump in `generate_config --append`,
  part of `apply_updates`) to leave `.env` owned by `root`, silently breaking every
  subsequent unprivileged run with a permission error reading `.env`. Root-caused on
  zoneserver after an accidental `sudo ./<slug>-update.sh` run. **Only affects newly
  generated scripts** — re-run `ophix-manage create_update_script` on each server to pick
  up the guard on an already-deployed `-update.sh`.

## 2026.07.07.02

- `DJANGO_SECRET_KEY`, `DB_PASSWORD`, and `BACKUP_PASSPHRASE` are now written to `.env`
  with single-quote wrapping (`quote_mode="always"`). Previously written unquoted, characters
  such as `$`, `!`, and `#` in these values could be misinterpreted when the file was
  `source`d by the backup script.

## 2026.07.07.01

- `import_env` now uses `--input-file FILE` instead of a positional argument, matching the
  convention used by all other `import_*` commands. Existing scripts that pass the filename
  as a bare positional argument must be updated to use `--input-file`.

## 2026.06.24.01

- `ClientAdmin.register_field_display(field_name, display_fn)` hook added — plugins can
  now register a custom readonly display function for any named field on the Client change
  view. The function replaces the raw field value with formatted HTML. Used by
  `ophix-client-management` to show token rotation state as a styled status indicator
  rather than a plain datetime.

## 2026.06.10.01

- Added `export_env` management command — encrypts the server's `.env` file with a
  passphrase (Fernet + PBKDF2) and writes a versioned `.env.enc` backup file. Requires
  `--passphrase` or `--passphrase-env`. See `server-backup.md` for the DR workflow.
- Added `import_env` management command — decrypts an `.env.enc` backup and writes it
  back to disk. `--install-dir PATH` patches `INSTALL_DIR` in the restored file (for
  restores to a different path). Prints a reminder to restart the service.
- `BACKUP_INCLUDE_CLIENT_LINKS` env comment changed from `true` → `True` for consistency
  with Python-style booleans across all Ophix env vars.
- `create_backup_script` now derives the suggested `BACKUP_PATH` from `INSTALL_DIR` when
  available: `INSTALL_DIR.parent / "backups" / INSTALL_DIR.name` (e.g.
  `/home/user/ophix/taskserver` → `/home/user/ophix/backups/taskserver`).
- `nginx.conf.j2` now includes `error_page` directives for 400, 403, 404, 500/502, and
  503/504 — pointing to static HTML files generated by `generate_error_pages` in
  `ophix-admin-interface`. The 503 page is served directly from the static alias even
  when Gunicorn is down.
- `run_install` step 12: calls `generate_error_pages` after documentation loading,
  writing themed error pages to `INSTALL_DIR/static/error_pages/`.
- `configure_install` now includes a "Backup" section — prompts for backup directory
  (BACKUP_PATH, derived from INSTALL_DIR), backup passphrase (hidden, with confirmation),
  and backup targets. Domain-aware defaults are set automatically from the detected domain
  plugin (e.g. `hosts,clients,settings,tasks` / `env` for ophix-tasks;
  `hosts,clients,settings` / `env,creds` for ophix-creds). Targets requiring a passphrase
  (env, certs_ca) are excluded from defaults when no passphrase is set. All settings are
  written to `.env` by `_write_env`.
- `run_install` step 13: creates the backup directory and generates the backup script when
  `BACKUP_PATH` is configured.
- Updated `server-backup.md` with `export_env` / `import_env` documentation and DR
  restore workflow, and with `configure_install` automatic backup setup docs.

## 2026.06.09.04

- `create_backup_script` now names the generated script `<server_name>-backup.sh`
  (e.g. `taskserver-backup.sh`) instead of `ophix-backup.sh`, so deployments with
  multiple servers produce distinctly named scripts.
- Added `--compress` flag to the generated backup script: after all exports complete,
  the `.json` files are bundled into `<server_name>_<timestamp>.tgz` and removed,
  leaving a single portable archive. The suggested cron entry now includes `--compress`.
- Updated `server-backup.md` to document the naming convention and `--compress` flag.

## 2026.06.09.03

- Added `create_backup_script` management command — generates `ophix-backup.sh` in the
  current directory. The script sources `.env` at runtime, reads `BACKUP_TARGETS` and
  `BACKUP_TARGETS_ENCRYPTED` to determine which domain exports to run, auto-detects
  whether each export is available on this server, and bakes in the `ophix-manage` path
  from the running venv. Re-run after upgrading or moving the venv. See each domain's
  backup docs for the recommended `BACKUP_TARGETS` / `BACKUP_TARGETS_ENCRYPTED` values.
- Added "Scheduled backups" section to `env.sample.j2` with `BACKUP_PATH`,
  `BACKUP_TARGETS`, `BACKUP_TARGETS_ENCRYPTED`, `BACKUP_PASSPHRASE`, and
  `BACKUP_INCLUDE_CLIENT_LINKS` entries.
- Added "Scheduled backups" section to `server-backup.md` with base `.env` values
  (`BACKUP_TARGETS=hosts,clients,settings`) and a note to check domain docs for
  domain-specific targets.
- `ophix-admin-settings` added to `dependencies` in `pyproject.toml` — `run_install` imports `ophix_admin_settings` and the dependency was previously implicit.
- One-time token display on the Client add form: `ClientAdmin.add_view` pre-generates a plaintext token on GET and carries it through POST via the session; the token is shown inline on the add form (inside a styled warning card with a Copy button) before the operator saves. On save, `save_model` pops the session token, hashes it, and persists the hash — the plaintext is never stored.
- "Issue a replacement token" flow for existing clients: `api_token_display` read-only field on the change form shows hash dots plus a red "Issue a replacement token…" button linked to `<pk>/change-token/`. `change_token_view` handles GET (confirmation page) and POST (generate + save new token, render `token_created.html`). The replacement token page is shown as a Magnific Popup iframe and reloads the parent on close to reflect the updated `last_token_rotation`.
- New templates: `admin/ophix_core/client/token_created.html` (one-time token display for the replacement flow; popup + non-popup modes with working nav sidebar), `admin/ophix_core/client/change_form.html` (inline token card on add), `admin/ophix_core/client/change_token_confirm.html` (replacement confirmation warning).

## 2026.06.05.04

- `export_clients`, `export_hosts`: export file now includes a `meta` block with `created_at`, `server_name`, `server_version`, `hostname`, `domain`, `command`, `run_by`, `login_user`, and `ssh_origin`.
- `export_hosts`: output format changed from a bare JSON array to a versioned payload dict (`version`, `meta`, `hosts`). `import_hosts` updated accordingly.
- `export_clients`, `import_clients`: `--passphrase` now accepts no value to prompt securely (export confirms twice); `--passphrase-env ENVVAR` reads the passphrase from an environment variable for automated use. Both options are mutually exclusive.

## 2026.06.02.01

- `DeleteRedirectToChangelistMixin` added to `ophix.core.admin`. Apply to any read-only admin that still permits deletion to redirect post-delete to the changelist rather than admin:index (which shows the custom home page). Applied to `AccessLogAdmin`.
- Fixed stale `django-admin-interface` reference in `env.sample.j2` — corrected to `ophix-admin-interface`.
- Plugin loader now supports `CONTEXT_PROCESSORS_APPEND` — a list of dotted-path
  context processor strings that a plugin contributes to the DjangoTemplates backend.
  Used by `ophix-admin-settings` to inject `server_settings` into every admin template
  context. Multiple plugins may each contribute processors; they accumulate safely.
- Fixed `AttributeError` in `manage.py` when a hidden command (e.g. `makemigrations`)
  was attempted: `_filtered_fetch` used `self.stderr` which does not exist on
  `ManagementUtility`. Changed to `sys.stderr.write`.

## 2026.05.30.05

- Added `lockout_override` field to `Client` model (migration 0010). Set by the token-policy Unlock action to grant a locked-out client a **restricted** authentication bypass: only `/api/client/self/` endpoints (info, update, rotate-token) are accessible while the override is active. Domain artifact endpoints remain blocked until a real token rotation completes. Cleared automatically on successful token rotation.

## 2026.05.30.04

- Admin sidebar section renamed from "Clients & Hosts" to "Hosts & Clients"; Hosts now appears above Clients (general before specific).

## 2026.05.30.03

- `configure_install` and `configure_database` now handle Ctrl+C gracefully — prints "Cancelled." instead of a stack trace.

## 2026.05.30.02

- Added inline documentation page "Server Backup and Migration" covering
  `export_hosts`, `import_hosts`, `export_clients`, and `import_clients`,
  including restore dependency order, encryption details, and migration vs.
  disaster recovery workflows.

## 2026.05.30.01

- `apply_updates` now accepts `--include-docs`: auto-discovers all installed
  modules with a `docs/` directory and runs `update_docs` for them in one step.

## 2026.05.28.02

- `check_updates` now uses `pip list --outdated` instead of one `pip index versions` subprocess
  per package. A single pip call replaces N subprocesses, making the command significantly faster.

## 2026.05.28.01

- Token lockout enforcement in `ClientTokenAuthentication`: when `TOKEN_LOCKOUT_DAYS` is set
  and a client's token age meets or exceeds it, API access is denied until an operator unlocks
  the client via the token-policy dashboard. Set `TOKEN_LOCKOUT_DAYS=0` to disable (default).
  A value below `TOKEN_REQUIRE_DAYS` is invalid and is ignored with a log warning. Clients
  that have never rotated are not subject to lockout.

## 2026.05.27.01

- Release Notes fieldset in the Package Update Record detail view is now collapsed by default.

## 2026.05.26.01

- Updated copyright footer link in `base_site.html` from ophixproject.com to ophix.io

## 2026.05.22.08

- `generate_ophix_config` renamed to `generate_config` — `_ophix_` infix removed
  for consistency with all other management commands. Update any cron jobs or scripts
  that reference the old name.

## 2026.05.22.06

- Added `SERVER_READ_ONLY_MODE` setting (default `False`). When `True`, all
  API write requests (POST/PUT/PATCH/DELETE to `/api/`) are rejected with
  HTTP 503 — blocking registrations, token rotations, and artifact updates.
  Reads, admin access, and internal logging are unaffected. Use during a
  migration change window: set on the source server before exporting, leave
  unset on the target, then update DNS. Clients treat 503 as transient and
  retry on their next cycle.

- Added `export_hosts` / `import_hosts` commands — transfer Host records between
  servers. Idempotent (matched by name), cron-safe. Both support `--dry-run`,
  `--quiet`; `import_hosts` supports `--force` to bypass IP conflict checks.
- Added `export_clients` / `import_clients` commands — backup and restore Client
  records including tokens, enabling fleet clients to reconnect to a rebuilt
  server without re-registering. `export_clients` accepts `--passphrase` to
  encrypt tokens using a PBKDF2-derived Fernet key (salt stored in file);
  `import_clients` requires the same passphrase if the file is encrypted and
  validates the key before touching the database. Both support `--dry-run`,
  `--quiet`; `import_clients` supports `--force` to bypass token conflict checks.
  Run `import_hosts` before `import_clients` when doing a full server restore.

## 2026.05.22.05

- Fixed `apply_updates` always printing `taskserver` (or the SERVER_NAME slug)
  instead of the actual service name: `SERVICE_NAME` was written to `.env` by
  `run_install` but never loaded into Django settings. Added
  `SERVICE_NAME = os.getenv("SERVICE_NAME", "")` to `settings/base.py`.

## 2026.05.22.04

- Added migration 0008: `PackageUpdateRecord.first_recorded_at` help text updated
  to reference `check_updates` (was `check_ophix_updates`).

## 2026.05.22.03

- Fixed crash when running any management command after the hidden-command patch
  was applied: `get_commands` was replaced globally, breaking Django's internal
  system check that looks up `makemigrations` before dispatch. The patch now
  targets `ManagementUtility.fetch_command` (blocks hidden commands at execution)
  and `ManagementUtility.main_help_text` (filters --help display) instead of
  replacing `get_commands`, leaving Django internals unaffected.

## 2026.05.22.02

- Management commands renamed — `ophix_` infix removed as redundant within
  `ophix-manage` context: `check_ophix_updates` → `check_updates`,
  `list_ophix_plugins` → `list_plugins`, `apply_ophix_updates` → `apply_updates`.
- `prune_access_log` renamed to `prune_access_logs` for consistency with
  `archive_access_logs` and `prune_task_logs`.

## 2026.05.22.01

- `generate_deploy_config` renamed to `generate_ophix_config` (further renamed
  to `generate_config` in a later release).
- `apply_updates` renamed to `apply_ophix_updates` for consistent namespacing.
- `init_deploy` removed — fully superseded by `configure_install` + `run_install`.
- `run_install` now writes `SERVICE_NAME` to `.env` so that `apply_ophix_updates`
  can print the correct `systemctl restart` command even when the install slug
  differs from `SERVER_NAME`. Existing installs can add `SERVICE_NAME=<slug>`
  to `.env` manually to get the same behaviour.

## 2026.05.21.06

- `archive_access_logs` now accepts `--quiet` to suppress all output. Useful
  when running the archive-then-prune cron pattern alongside `prune_access_logs
  --quiet`. `--dry-run` output is always shown regardless of `--quiet`.
- `prune_access_logs` now accepts `--quiet` to suppress all output, making it
  safe to run from cron without generating noise in the mail spool. `--dry-run`
  output is always shown regardless of `--quiet`.

## 2026.05.21.05

- Added `archive_access_logs` command — exports `AccessLog` records to a file
  for long-term retention or compliance. Writes a JSON array by default;
  `--append` writes newline-delimited JSON (NDJSON) suitable for incremental
  cron runs. Defaults to 90 days (or `PRUNE_ACCESS_LOG_DAYS`); use `--all`
  to export every record (e.g. incident snapshot).
- `prune_access_logs` now accepts `--all` to explicitly delete every record,
  making the intent clearer than `--days 0`.
- `prune_access_logs` now reads its default retention period from the
  `PRUNE_ACCESS_LOG_DAYS` setting (configurable in `.env`). Falls back to
  90 days if not set. `--days` on the command line always takes precedence.
- `check_ophix_updates --quiet` now also suppresses the per-package progress
  lines written to stderr, not just the table output.

## 2026.05.21.04

- Fixed `ophix-manage` auto-chdir: previous fix used `sys.executable` which
  resolves symlinks on Linux and could point outside the venv entirely.
  Switched to `sys.prefix` which is always the venv directory with no
  symlink ambiguity, making the `.env` lookup reliable on all platforms.
- `apply_updates` completion message now prompts to review `.env` for new
  variables before restarting the service.

## 2026.05.21.03

- Added `apply_updates` management command — convenience wrapper that runs
  `migrate`, `collectstatic --noinput`, and `generate_config --append`
  in sequence after a `pip install --upgrade`. Prints a `systemctl restart`
  reminder with the correct service name at the end.

## 2026.05.21.02

- `ophix-manage` now automatically changes to the server root directory on
  startup so that `find_dotenv` always locates `.env` regardless of the
  working directory the command was invoked from. Fixes DB connection errors
  when running `ophix-manage` commands from cron or an arbitrary path.
- Fixed `check_ophix_updates --help` crash on Python 3.12: command `help`
  strings were using `gettext_lazy` which `re.sub` refuses to accept as a
  string in 3.12. Switched to `gettext` (eager evaluation).

## 2026.05.21.01

- Bug fix, remove incorrectly wrapped test in check_ophix_update management command

## 2026.05.19.13

- Added migration 0007: `PackageUpdateRecord` singular `verbose_name` changed
  to "Plugin" — admin now reads "Select Plugin to View" / "View Plugin".

## 2026.05.19.12

- Added migration 0006: records `verbose_name` and `help_text` change on
  `PackageUpdateRecord.notice` (renamed to "release notes" in 2026.05.19.07).
- `PackageUpdateRecord` singular `verbose_name` changed to "Plugin" so the
  admin reads "Select Plugin to View" / "View Plugin".

## 2026.05.19.11

- Fixed migration 0005 dependency: app label must be `ophix_core`, not `core`.

## 2026.05.19.10

- Added `ipv6_address` field to `Host` model (nullable, unique). `ipv4_address`
  is now also nullable — at least one address is required (enforced in `clean()`).
  Auth checks the incoming IP against whichever addresses are registered.
- Added `SHOW_IPV6_ADDRESS` setting (default `True`). Set to `False` on
  IPv4-only networks to hide the column and keep the Hosts list uncluttered.

## 2026.05.19.09

- Release notes rendered with scoped CSS (`.ophix-release-notes`): version
  headers display as lightweight link-coloured dividers rather than picking up
  Django admin's fieldset `h2` styling.

## 2026.05.19.08

- Renamed model display name from "Package Update Records" to "Plugin Versions".
- Renamed `SHOW_PACKAGE_UPDATE_MODEL` env var to `SHOW_PLUGIN_VERSION_MODEL`.

## 2026.05.19.07

- `PackageUpdateRecord` detail view: added `fieldsets` to suppress the raw
  `update_available` boolean field (which showed Django's default red ✗ icon);
  the themed `Up To Date` column is the only status indicator now.
- Renamed `notice` field label to "Release Notes"; updated help text to describe
  the field accurately (populated from `OPHIX_RELEASE_NOTES.md` at check time).
- Release notes are now rendered as markdown in the detail view (`markdown`
  package added as a dependency).

## 2026.05.19.06

- Fixed `UnboundLocalError` in `check_ophix_updates --prune`: `_` used as a
  throwaway in tuple unpacking shadowed the `gettext_lazy` alias for the
  entire `handle()` method. Changed to index access (`.delete()[0]`).

## 2026.05.19.05

- `check_ophix_updates`: added `--prune` flag to remove `PackageUpdateRecord`
  rows for packages that are no longer installed.
- Fixed `TypeError` in `PackageUpdateRecord` admin list view on Django 6.0.4+
  (`format_html` now requires at least one argument; static HTML uses `mark_safe`).

## 2026.05.19.04

- `PackageUpdateRecord` detail view is now read-only; release notes from each
  package's `OPHIX_RELEASE_NOTES.md` are displayed in the notice field.
- Package Update Records admin: renamed "Update Available" column to "Up To Date"
  with inverted logic; replaced Django's default tick/cross icons with
  theme-aware ✓ and ⬆ indicators.

## 2026.05.19.03

- Added `check_ophix_updates` management command — checks all installed Ophix
  plugins against the configured pip index and reports available updates.
- Added `PackageUpdateRecord` model — stores per-package update state and
  release notes. Enable the admin view with `SHOW_PLUGIN_VERSION_MODEL=True`.
- Added `SHOW_PLUGIN_VERSION_MODEL` setting (default `False`).

## 2026.05.18.03

- Forked `django-admin-interface` as `ophix-admin-interface`. Existing
  installations are data-compatible — no fixture changes required.
- Row-state colouring in list views (paused/disabled) now derives colours
  from theme CSS variables rather than hardcoded values.

## 2026.05.18.02

- Fixed missing `python-slugify` dependency in `ophix-admin-interface`.

## 2026.05.18.01

- Added migration 0034: `help_text` on `custom_css_vars` field.
