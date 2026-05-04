# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Ophix platform.

ADRs capture significant decisions — especially the *why* behind them, including rejected alternatives. The goal is to give future contributors (and future sessions) enough context to understand a decision without having to reconstruct it from code history.

## Scope

This directory covers **cross-cutting decisions** that affect multiple packages or the platform as a whole. Package-specific decisions may live in a `docs/decisions/` directory within the relevant package repo.

## Format

Each ADR is a markdown file named `ADR-NNN-short-title.md`. Status values: `Accepted`, `Superseded`, `Deprecated`.

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-versioning-convention.md) | Date-based version strings | Accepted |
| [ADR-002](ADR-002-plugin-entry-point-system.md) | Plugin discovery via entry points | Accepted |
| [ADR-003](ADR-003-dual-token-ip-authentication.md) | Dual token + IP authentication | Accepted |
| [ADR-004](ADR-004-client-cli-option-naming.md) | Tier 1 client CLI option naming | Accepted |
| [ADR-005](ADR-005-domain-independence.md) | Domain independence and no cross-domain coupling | Accepted |
| [ADR-006](ADR-006-rbac-django-groups.md) | RBAC for admin UI using Django groups | Accepted — not yet implemented |
