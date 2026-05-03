# ADR-001: Date-based version strings

**Date:** 2026-03-01 (approx)
**Status:** Accepted

## Context

Ophix packages need version numbers. Semantic versioning (MAJOR.MINOR.PATCH) was the obvious default but creates friction in a project where:

- Every package is independently deployable
- Packages don't have a public API contract to preserve in the SemVer sense — they're infrastructure tools for a specific fleet
- The meaningful question for an operator is "how old is this?" not "does this have breaking changes?"
- Multiple releases on the same day happen regularly during development

SemVer also requires deciding what counts as "breaking" — a judgement call that invites inconsistency across packages.

## Decision

All packages use `YYYY.MM.DD.NN` where `NN` is a daily sequence number starting at `01`.

Every package includes:
- `src/<module>/_version.py` — contains `__version__ = "YYYY.MM.DD.NN"`, committed and ships with the installed package
- `gen_version.py` in the repo root — reads version from `pyproject.toml` and writes `_version.py`. Run after bumping `pyproject.toml`.

## Consequences

- Operators can immediately tell how current an installation is without consulting a changelog
- No "what counts as breaking?" debates
- `list_ophix_plugins --details` can display meaningful version information across all installed packages
- Versions are not comparable in a compatibility sense — operators must read release notes for upgrade guidance
- Daily sequence numbers reset per-package, not globally, so `2026.05.03.02` in two different packages are unrelated
