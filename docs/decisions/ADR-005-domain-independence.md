# ADR-005: Domain independence and no cross-domain coupling

**Date:** 2026-03-01 (approx)
**Status:** Accepted

## Context

Ophix manages multiple domains: credentials, configurations, certificates, DNS zones, tasks, and more. As the platform grows, there are natural temptations to reuse functionality across domains — for example, having a certificate server fetch its CA encryption key from a credential server, or having a configuration server push configs directly to a certificate server.

These integrations would reduce boilerplate but would also mean a domain server could not run unless another domain server was also running and reachable.

## Decision

Every server-client pair must be able to run in complete isolation. No domain may depend on another domain being installed or running.

Concretely:
- No domain server imports from or calls another domain server
- No Tier 1 client has a hard dependency on another Tier 1 client
- Synergies between domains are implemented in Tier 2 clients with **local fallbacks** for every Ophix integration

The fallback requirement is what makes multi-domain Tier 2 clients (e.g. `ophix-acme`) compliant — each integration (cred-client for EAB credentials, zone-client for DNS-01 challenges) is optional, and the tool continues to function using local config files if those integrations are absent.

This rule is non-negotiable.

## Consequences

- Any Ophix server can be deployed standalone without touching other domains
- Fleet members that only need credentials don't need a certificate server
- Air-gap deployments and minimal installations are always possible
- Some duplication exists across domains (e.g. each domain has its own auth, its own token rotation) — this is the intended cost of independence
- `ophix-acme` is the canonical example of the correct multi-domain pattern: optional integrations with local fallbacks, not hard dependencies
- If a future tool *requires* another domain to be running, it is coupling, not synergy — reject it and redesign with a fallback
