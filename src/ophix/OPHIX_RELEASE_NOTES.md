# ophix-server-base Release Notes

## Unreleased

- `run_install` now writes `SERVICE_NAME` to `.env` so that `apply_updates`
  can print the correct `systemctl restart` command even when the install slug
  differs from `SERVER_NAME`. Existing installs can add `SERVICE_NAME=<slug>`
  to `.env` manually to get the same behaviour.

## 2026.05.21.06

- `archive_access_logs` now accepts `--quiet` to suppress all output. Useful
  when running the archive-then-prune cron pattern alongside `prune_access_log
  --quiet`. `--dry-run` output is always shown regardless of `--quiet`.
- `prune_access_log` now accepts `--quiet` to suppress all output, making it
  safe to run from cron without generating noise in the mail spool. `--dry-run`
  output is always shown regardless of `--quiet`.

## 2026.05.21.05

- Added `archive_access_logs` command — exports `AccessLog` records to a file
  for long-term retention or compliance. Writes a JSON array by default;
  `--append` writes newline-delimited JSON (NDJSON) suitable for incremental
  cron runs. Defaults to 90 days (or `PRUNE_ACCESS_LOG_DAYS`); use `--all`
  to export every record (e.g. incident snapshot).
- `prune_access_log` now accepts `--all` to explicitly delete every record,
  making the intent clearer than `--days 0`.
- `prune_access_log` now reads its default retention period from the
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
  `migrate`, `collectstatic --noinput`, and `generate_deploy_config --append`
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
