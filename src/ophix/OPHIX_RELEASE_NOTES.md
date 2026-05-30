# ophix-server-base Release Notes

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
