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

## Follow-up (2026-11-20): source IP no longer read from X-Forwarded-For

The original implementation took the leftmost `X-Forwarded-For` entry as the source IP, and the generated nginx config forwarded that header with `$proxy_add_x_forwarded_for`, which *appends* to whatever the client sent. On a stock install, with no load balancer involved, any client could therefore choose its own apparent IP by sending one header. That reduced token+IP authentication to token-only and let anyone who could reach the server register a client (or, in `ophix-zones`, a DNS server) against any registered Host. The "load balancers must strip and re-set X-Forwarded-For" consequence above described only part of the exposure.

Changes:

- `ophix.core.utils.get_client_ip()` is the single place the source IP is decided, and every caller uses it (core auth and registration, `ophix-zones` auth and registration). It reads `X-Real-IP` (set by nginx to `$remote_addr`, overwriting any client value), falls back to `REMOTE_ADDR`, and never parses `X-Forwarded-For`.
- The generated nginx config sets `X-Forwarded-For` to `$remote_addr` instead of appending to it.
- Trust in upstream proxies is configured in nginx, not Django: `configure_install`'s trusted-upstream-proxies prompt (`[nginx] trusted_proxies`) renders `set_real_ip_from` / `real_ip_header X-Forwarded-For` / `real_ip_recursive on`, so `$remote_addr` is already the real client address when a load balancer is in front.
- `ophix-zones`' `/api/dns-register/` no longer accepts a caller-chosen `host_ip`; a supplied value must equal the source IP.

The consequence above should now read: a load balancer or reverse proxy in front of nginx must be listed as a trusted upstream proxy, and the nginx config must never be edited to trust `X-Forwarded-For` from arbitrary sources.
