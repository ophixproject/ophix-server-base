# ADR-003: Dual token + IP authentication

**Date:** 2026-03-01 (approx)
**Status:** Accepted

## Context

Fleet clients need to authenticate with the server. Standard token authentication (Authorization header) is straightforward but has a well-known weakness: a token leaked from a backup, log file, or compromised host is usable from anywhere.

Options considered:

1. **Token only** — simple, widely understood, but a stolen token is immediately exploitable from any IP.
2. **mTLS** — strong, but requires certificate management on every client, which is significant operational complexity for a fleet that may include low-privilege or ephemeral hosts.
3. **Token + source IP** — both must match the registered values. A stolen token is useless without the registered host IP.
4. **Token + HMAC request signing** — strong but adds client-side complexity and replay-attack considerations.

## Decision

Every authenticated API request requires:
- `Authorization: Token <64-char hex token>` header
- Source IP matching the client's registered Host record

Both conditions must pass. Failure of either returns the same generic error response (no distinction between bad token vs wrong IP) when `AUTH_LEAK_INFO=False` (the production default).

This is implemented in `ophix.core.auth.ClientTokenAuthentication` and is applied to all authenticated endpoints across all domain plugins.

The security properties this provides:
- A stolen token from a backup or log is not exploitable without also controlling the registered IP
- A compromised host's token cannot be used from an attacker's machine
- Revocation operates at multiple levels: individual client-artifact link, entire client, or entire host

This rule is non-negotiable and must never be relaxed for API endpoints.

## Consequences

- Clients must run on the registered IP — dynamic IPs require re-registration or Host record updates
- Load balancers and proxies must strip and re-set `X-Forwarded-For` before requests reach nginx, otherwise clients on internal networks could spoof their source IP
- The `AUTH_LEAK_INFO=False` default means authentication failures are opaque in production — intentional to prevent fingerprinting
- Scheduled token rotation is load-bearing security infrastructure (not optional nicety) — a captured token has a bounded useful lifetime
