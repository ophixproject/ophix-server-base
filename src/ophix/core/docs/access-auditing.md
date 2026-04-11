---
title: Access Auditing
slug: access-auditing
order: 10
section: Getting Started
---

Every Ophix server records a log of client artifact access events. The audit log is built into `ophix-server-base` and requires no additional configuration — it is active in all domain servers (credentials, configurations, certificates, and any future domains).

---

## What is logged

Each time a client successfully reads or writes an artifact, an `AccessLog` record is created with:

| Field | Description |
| --- | --- |
| `client` | The client that made the request |
| `host` | The host the client is running on |
| `operation` | `GET` (read) or `POST` (write/create) |
| `artifact_type` | Model class name — `Credential`, `CertBundle`, etc. |
| `artifact_name` | Artifact name at the time of access (snapshot — survives renames and deletions) |
| `artifact_id` | Artifact primary key at the time of access (survives artifact deletion) |
| `timestamp` | Time of the request (set when the event is created, not when it is written to the database) |

Only successful operations are logged. Requests that are rejected by authentication or permission checks are not recorded in the access log (they appear in the application log via standard Django logging).

---

## Viewing the audit log

The access log is available in the Django admin under **Ophix Core → Access Logs**.

The list view supports filtering by:

- Client
- Host
- Operation (GET / POST)
- Artifact type
- Date (date hierarchy navigation)

The log is read-only — records cannot be added, edited, or deleted through the admin.

---

## Performance

The audit writer is non-blocking by design. Domain views put events on an in-memory queue and return immediately — the request thread never waits for a database write. A background daemon thread drains the queue and writes batches using a single `bulk_create()` call.

If the queue fills up under extreme load, excess events are dropped and a warning is written to the application log. Auditing never adds back-pressure to primary request serving.

---

## Settings

| Variable | Default | Description |
| --- | --- | --- |
| `AUDIT_BATCH_SIZE` | `50` | Number of events to accumulate before writing a batch to the database. |
| `AUDIT_FLUSH_INTERVAL` | `5` | Maximum seconds to wait before flushing a partial batch. Ensures events are not held indefinitely when traffic is light. |

These can be set in `.env`. For most deployments the defaults are appropriate.

---

## Pruning old records

Access log records accumulate indefinitely unless pruned. Use the `prune_access_log` management command to delete old records:

```bash
# Delete records older than 90 days (default)
ophix-manage prune_access_log

# Delete records older than 30 days
ophix-manage prune_access_log --days 30

# Preview how many records would be removed
ophix-manage prune_access_log --dry-run
ophix-manage prune_access_log --days 30 --dry-run
```

Run this on a schedule — a daily or weekly cron job is typical:

```cron
0 3 * * 0   ophixuser  /path/to/venv/bin/ophix-manage prune_access_log --days 90
```

Always run `--dry-run` first on a production server before adjusting the retention period to confirm the expected number of records will be removed.
