# ADR-004: Tier 1 client CLI option naming

**Date:** 2026-05-03
**Status:** Accepted

## Context

During testing of `ophix-conf-client` and `ophix-cred-client` in May 2026, inconsistent option naming was discovered across commands:

- `import` used `--env` to refer to a local env file variable
- `check` used `--var` for the same concept
- Help text used `ENV_VAR`, `ENV_KEY`, and `env_key` interchangeably
- `fetch` had no env-var lookup at all — only a required positional name argument

This made the CLI harder to learn and prevented building consistent mental models across commands and clients.

## Decision

All Tier 1 domain client CLIs standardise on two option names:

| Option | Meaning |
|---|---|
| `--name <n>` | The artifact name on the remote server |
| `--var <VAR>` | A key in the local `.domain.env` file whose value is the artifact name |

### fetch

`--name` and `--var` form a **mutually exclusive required group**. No positional argument.

```
<domain>-client fetch {--name <n>|--var <VAR>}
```

### import

Both options are independent (not mutually exclusive). Three usage modes:

| Flags | Behaviour |
|---|---|
| `--name` only | Use given name. No local env file changes. |
| `--var` only | Read name from local env file. Fail if var is not set. |
| `--name` + `--var` | Use given name AND write `VAR=name` to local env file. Refuse if `VAR` already maps to a different name. |

### check

`--all`, `--name`, and `--var` form a mutually exclusive required group. This was already correct and is preserved.

### What to avoid

- Never use `--env` or `--env-key` — these were the pre-standardisation names
- Never use a bare positional argument for the artifact name in fetch

## Consequences

- All current and future clients have the same mental model: `--name` = server-side, `--var` = local env file
- The `--name` + `--var` combination on `import` is the recommended one-step setup workflow for Tier 2 consumers
- **Exception:** `cert-client` uses positional `bundle` + `role` arguments because certificate access is role-based, not name-based. This exception is intentional and does not violate the spirit of the rule.
- `--var` aligns with `check --var`, which was already the correct form, so existing `check` usage is unaffected
