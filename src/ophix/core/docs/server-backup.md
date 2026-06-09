---
title: Server Backup and Migration
slug: server-backup
order: 40
section: Getting Started
---

Ophix provides management commands for exporting and importing the host and client records that form the foundation of every server instance. These are the starting point for any backup or migration workflow — domain-specific data (credentials, configurations, certificates) is covered in the documentation for each domain plugin.

---

## What gets exported

Ophix server state is split into layers. The base layer — managed by `ophix-server-base` — contains:

- **Hosts** — registered machines in the fleet, identified by name and IP address
- **Clients** — named automation processes on a host, each holding an API token

Domain plugins add their own artifact layer on top (credentials, configs, certs, etc.).

The restore dependency order is always:

```text
import_hosts  →  import_clients  →  import_<domain>
```

Hosts must exist before clients, and clients must exist before domain artifacts with client links.

---

## Exporting hosts

```bash
ophix-manage export_hosts --output-file hosts.json
```

Preview without writing:

```bash
ophix-manage export_hosts --output-file hosts.json --dry-run
```

The export file is a JSON array of host records. Host records contain no secrets and are always exported in plaintext.

| Flag | Description |
| --- | --- |
| `--output-file FILE` | _(required)_ Destination path |
| `--dry-run` | Show how many hosts would be exported without writing |
| `--quiet` | Suppress all output |

---

## Importing hosts

```bash
ophix-manage import_hosts --input-file hosts.json
```

Hosts are matched by name. Existing hosts are updated only when a field value differs; identical records are skipped. The import is safe to re-run.

```bash
ophix-manage import_hosts --input-file hosts.json --dry-run
```

By default the command checks for IP address conflicts — if an IP in the import file is already assigned to a differently-named host, the record is skipped with an error. Use `--force` to bypass this check when you know the conflict is safe to overwrite (e.g. the conflicting host is being decommissioned).

| Flag | Description |
| --- | --- |
| `--input-file FILE` | _(required)_ Source path (JSON produced by `export_hosts`) |
| `--dry-run` | Show what would be created or updated without making any changes |
| `--quiet` | Suppress per-record output; summary line always shown |
| `--force` | Bypass IP conflict checks |

---

## Exporting clients

```bash
ophix-manage export_clients --output-file clients.json
```

Preview without writing:

```bash
ophix-manage export_clients --output-file clients.json --dry-run
```

Client tokens are stored as SHA-256 hashes — the server never holds the plaintext after registration. The export file contains these hashes, not usable credentials. Standard filesystem permissions are sufficient to protect the file; no passphrase is required or offered.

| Flag | Description |
| --- | --- |
| `--output-file FILE` | _(required)_ Destination path |
| `--dry-run` | Show how many clients would be exported without writing |
| `--quiet` | Suppress all output |

---

## Importing clients

```bash
ophix-manage import_clients --input-file clients.json
```

Clients are matched by host name + client name. Existing clients are updated when any field differs; token hashes are always written on update (this is intentional — restoring a client's token hash is the point of the import). The import is idempotent.

Run `import_hosts` first — if a referenced host does not exist, the client record is skipped with an error.

Fleet clients reconnect to the restored server without re-registering. They still send the same plaintext bearer token they have always held; the server hashes it on each request and compares to the restored hash.

| Flag | Description |
| --- | --- |
| `--input-file FILE` | _(required)_ Source path (JSON produced by `export_clients`) |
| `--dry-run` | Show what would be created or updated without making any changes |
| `--quiet` | Suppress per-record output; summary line always shown |
| `--force` | Bypass token uniqueness checks (use when a token conflict exists with a differently-named client on this server) |

---

## Full base-layer restore workflow

This covers hosts and clients only. Follow this with the domain-specific import for a complete server restore.

```bash
# 1. Export from the source server
ophix-manage export_hosts --output-file hosts.json
ophix-manage export_clients --output-file clients.json

# 2. Transfer hosts.json and clients.json to the target server

# 3. Import on the target server
ophix-manage import_hosts --input-file hosts.json
ophix-manage import_clients --input-file clients.json
```

Fleet clients reconnect to the restored server without re-registering — their token hashes are preserved, and the client still holds the original plaintext token that maps to those hashes.

---

## Server migration vs. disaster recovery

**Migration** (planned move to new hardware or infrastructure):

1. Export from the source server while it is still running
2. Stand up the target server and run migrations
3. Import hosts, clients, and domain data
4. Switch DNS or update client configs to point to the target
5. Verify clients reconnect, then decommission the source

**Disaster recovery** (source server lost):

1. Restore from the most recent export files
2. Clients that rotated their tokens after the last export will need to re-register — the restored hash reflects the old token, which the client no longer holds. Rotation intervals shorter than your backup cadence minimise this window.

For a full Ophix server backup strategy, schedule exports from cron and store output files off-server with appropriate access controls.

---

## Scheduled backups

`ophix-manage create_backup_script` generates `<server_name>-backup.sh` (e.g. `taskserver-backup.sh`) — a cron-ready wrapper that reads `BACKUP_TARGETS` and `BACKUP_TARGETS_ENCRYPTED` from `.env` and runs the corresponding export commands. Re-generate after upgrading or moving the venv to refresh the baked-in `ophix-manage` path.

Add these entries to `.env` for the base server layer:

```ini
BACKUP_PATH=/home/ophix/backups/taskserver
BACKUP_TARGETS=hosts,clients,settings
BACKUP_PASSPHRASE=your-passphrase
```

**Keep `BACKUP_PATH` outside the install directory** and use a shared `backups/` folder subdivided by server name:

```text
/home/ophix/
  taskserver/           ← INSTALL_DIR  (removed on uninstall)
  credserver/           ← INSTALL_DIR
  backups/
    taskserver/         ← BACKUP_PATH for taskserver
    credserver/         ← BACKUP_PATH for credserver
```

The uninstall script removes the entire install directory. Backups inside that tree go with it. A parallel `backups/<server>/` structure also prevents simultaneous cron runs from writing colliding filenames — all servers export identically named files (`hosts_<timestamp>.json` etc.) and with `--compress` the bundling step would pick up files from the wrong server if both ran into the same directory at the same second.

`hosts`, `clients`, and `settings` contain no secrets — client tokens are SHA-256 hashes. They always go in `BACKUP_TARGETS` regardless of server type. See the backup documentation for your installed domain to add the domain-specific target.

Pass `--compress` to bundle all exported `.json` files into a single dated `.tgz` and remove the originals:

```bash
taskserver-backup.sh --compress
```

The typical cron entry:

```bash
0 2 * * * /home/ophix/taskserver/taskserver-backup.sh --compress >> /var/log/ophix-backup.log 2>&1
```
