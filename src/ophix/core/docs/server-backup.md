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

```
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

Client records include API tokens — the secrets that fleet clients use to authenticate. Protect the output file accordingly.

**Export with encrypted tokens (recommended):**

```bash
ophix-manage export_clients --output-file clients.json --passphrase "your-passphrase"
```

**Export with plaintext tokens:**

```bash
ophix-manage export_clients --output-file clients.json
```

Without `--passphrase`, tokens are written in plaintext. The command prints a warning. This is a deliberate operator choice — the file must then be treated as a credential store.

Preview without writing:

```bash
ophix-manage export_clients --output-file clients.json --passphrase "your-passphrase" --dry-run
```

| Flag | Description |
| --- | --- |
| `--output-file FILE` | _(required)_ Destination path |
| `--passphrase PASSPHRASE` | Encrypt tokens using a PBKDF2-derived Fernet key |
| `--dry-run` | Show how many clients would be exported without writing |
| `--quiet` | Suppress all output |

### How token encryption works

When `--passphrase` is provided, each token is encrypted with a Fernet key derived from the passphrase via PBKDF2-HMAC-SHA256 (480,000 iterations). A random 16-byte salt is generated per export and stored in the file alongside the encrypted tokens. The passphrase is not stored anywhere — you must provide it again on import.

---

## Importing clients

```bash
ophix-manage import_clients --input-file clients.json --passphrase "your-passphrase"
```

If the file was exported without `--passphrase`:

```bash
ophix-manage import_clients --input-file clients.json
```

The passphrase is validated against the first token in the file **before** any database changes are made. If the passphrase is wrong, the command stops immediately with an error.

Clients are matched by host name + client name. Existing clients are updated when any field differs; tokens are always written on update (this is intentional — restoring a client's token is the point of the import). The import is idempotent.

Run `import_hosts` first — if a referenced host does not exist, the client record is skipped with an error.

| Flag | Description |
| --- | --- |
| `--input-file FILE` | _(required)_ Source path (JSON produced by `export_clients`) |
| `--passphrase PASSPHRASE` | Decrypt tokens (required if file was exported with `--passphrase`) |
| `--dry-run` | Show what would be created or updated without making any changes |
| `--quiet` | Suppress per-record output; summary line always shown |
| `--force` | Bypass token uniqueness checks (use when a token conflict exists with a differently-named client on this server) |

---

## Full base-layer restore workflow

This covers hosts and clients only. Follow this with the domain-specific import for a complete server restore.

```bash
# 1. Export from the source server
ophix-manage export_hosts --output-file hosts.json
ophix-manage export_clients --output-file clients.json --passphrase "your-passphrase"

# 2. Transfer hosts.json and clients.json to the target server

# 3. Import on the target server
ophix-manage import_hosts --input-file hosts.json
ophix-manage import_clients --input-file clients.json --passphrase "your-passphrase"
```

Fleet clients can reconnect to the restored server without re-registering, because their tokens are preserved.

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
2. Clients that rotated their tokens after the last export will need to re-register — their saved token will not match the restored one. Rotation intervals shorter than your backup cadence minimise this window.

For a full Ophix server backup strategy, schedule exports from cron and store output files off-server with appropriate access controls.
