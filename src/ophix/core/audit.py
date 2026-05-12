"""
ophix.core.audit
~~~~~~~~~~~~~~~~
Non-blocking access audit logging.

Public API
----------
record_access(access, operation)
    Drop an audit event on the queue and return immediately.
    Never blocks the calling request thread.

Design
------
A single daemon thread drains the queue and writes batches via bulk_create.
The thread starts lazily on the first call to record_access(), which avoids
issues with forking WSGI servers that start threads before fork.

If the queue is full, the event is silently dropped and a warning is logged.
Queue overflow means the server is under extreme load — auditing must never
add back-pressure to primary request serving.

Settings (in ophix.settings.base)
----------------------------------
AUDIT_BATCH_SIZE     — flush after N events (default 50)
AUDIT_FLUSH_INTERVAL — flush after N seconds even if batch not full (default 5)
"""

import logging
import queue
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_audit_queue: queue.Queue = queue.Queue(maxsize=1000)
_started: bool = False
_lock: threading.Lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_settings() -> tuple[int, int]:
    from django.conf import settings
    batch_size = getattr(settings, "AUDIT_BATCH_SIZE", 50)
    flush_interval = getattr(settings, "AUDIT_FLUSH_INTERVAL", 5)
    return int(batch_size), int(flush_interval)


def _build_event(access, operation: str) -> dict:
    """
    Extract and snapshot fields from the join record at the moment of the call.

    The artifact FK field name varies by domain. We discover it by inspecting
    the model's concrete fields for ForeignKeys that are not 'client', so new
    domains require no changes here.
    """
    client = getattr(access, "client", None)
    host = getattr(client, "host", None) if client else None

    artifact = None
    try:
        for field in access.__class__._meta.get_fields():
            if (
                hasattr(field, "many_to_one") and field.many_to_one
                and field.name != "client"
            ):
                candidate = getattr(access, field.name, None)
                if candidate is not None:
                    artifact = candidate
                    break
    except Exception:
        pass

    artifact_type = type(artifact).__name__ if artifact else ""
    artifact_name = str(getattr(artifact, "name", "")) if artifact else ""
    artifact_id = artifact.pk if artifact is not None else None

    return {
        "client": client,
        "host": host,
        "operation": operation,
        "artifact_type": artifact_type,
        "artifact_name": artifact_name,
        "artifact_id": artifact_id,
        "timestamp": datetime.now(tz=timezone.utc),
    }


def _writer_loop() -> None:
    """Drain the queue in batches and persist via bulk_create."""
    from ophix.core.models import AccessLog

    while True:
        batch_size, flush_interval = _get_settings()

        # Block until the first event arrives (or timeout)
        try:
            first = _audit_queue.get(timeout=flush_interval)
        except queue.Empty:
            continue

        batch = [first]

        # Drain additional queued events without blocking
        while len(batch) < batch_size:
            try:
                batch.append(_audit_queue.get_nowait())
            except queue.Empty:
                break

        try:
            AccessLog.objects.bulk_create([AccessLog(**ev) for ev in batch])
        except Exception:
            logger.exception(
                "Audit bulk_create failed — %d event(s) lost", len(batch)
            )


def _ensure_worker() -> None:
    """Start the daemon writer thread on the first call (thread-safe)."""
    global _started
    if _started:
        return
    with _lock:
        if _started:
            return
        t = threading.Thread(
            target=_writer_loop,
            name="ophix-audit-writer",
            daemon=True,
        )
        t.start()
        _started = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_access(access, operation: str) -> None:
    """
    Record a client artifact access event — non-blocking.

    Parameters
    ----------
    access : ClientArtifactBase subclass instance
        The join record (ClientCredential, ClientConfiguration,
        ClientCertAccess, etc.) — the artifact and client are read from it.
    operation : str
        "GET" or "POST"
    """
    _ensure_worker()
    try:
        event = _build_event(access, operation)
        _audit_queue.put_nowait(event)
    except queue.Full:
        client = getattr(access, "client", None)
        logger.warning(
            "Audit queue full — event dropped (client=%s op=%s)",
            client,
            operation,
        )
    except Exception:
        logger.exception("Audit record_access failed — event not queued")
