# ADR-007: Token hashing (SHA-256) and retention of custom auth

**Date:** 2026-06-07
**Status:** Accepted

## Context

Two questions were considered together because they are directly related:

1. **Should `Client.api_token` (and `DNSServer.api_token`) be stored as a hash rather than plaintext?**
2. **Should we replace `ClientTokenAuthentication` with DRF's built-in `TokenAuthentication`?**

### Token storage

`api_token` has been stored as a 64-character plaintext hex string since the beginning of
the project. Six months of active development produced zero situations where reading a token
from the server-side database was necessary — tokens flow outward at registration/rotation
and are never retrieved from the DB thereafter. Plaintext storage therefore provides no
operational benefit while creating meaningful risk: a database breach exposes every token,
even if they expire regularly. A token is functionally a password and should be treated
accordingly.

### DRF built-in TokenAuthentication

`rest_framework.authtoken` provides `TokenAuthentication`. The question arose whether using
an established, widely-audited implementation is preferable to maintaining a custom
`ClientTokenAuthentication`.

## Decision

### Token hashing — yes, SHA-256

`api_token` values are stored as SHA-256 hex digests of the plaintext token (64 chars →
64 chars, no schema change). The plaintext is generated server-side at registration and
returned to the client once; the server never holds it again. On subsequent requests the
server hashes the bearer token from the Authorization header and compares to the stored
hash.

SHA-256 was chosen over bcrypt/Argon2 because tokens have 256 bits of entropy — brute-force
is infeasible regardless of hash speed. There is no password-guessing attack surface to
harden against with a slow KDF.

Note: standard `rest_framework.authtoken` does **not** hash tokens (plaintext in DB). This
implementation improves on the DRF standard. `drf-knox` uses SHA-512; our SHA-256 is
functionally equivalent.

### Custom auth — keep it

`ClientTokenAuthentication` is retained. Switching to DRF's built-in auth is not viable
because:

1. **IP validation is non-negotiable.** Ophix's threat model requires both a valid token
   AND a matching source IP on every request (see ADR-003). DRF's `TokenAuthentication`
   validates the token only. Adding IP validation requires subclassing it — at which point
   you have custom auth anyway, with more indirection.

2. **Client ≠ Django User.** DRF tokens carry a `OneToOneField(User)`. Fleet `Client`
   objects are not Django users — they are named automation processes running on registered
   hosts. Mapping one to the other would require either a User-per-Client (conflates admin
   accounts with automation) or a fully custom `Token` model pointing at `Client`
   (equivalent complexity to the existing code).

3. **Enabled chain and lockout.** `client.enabled`, `client.host.enabled`,
   `TOKEN_LOCKOUT_DAYS`, and `lockout_override` are all enforced in the auth layer. None
   of these concepts exist in DRF's `TokenAuthentication`.

4. **Parallel DNSServer auth.** `DNSServerTokenAuthentication` authenticates against the
   `DNSServer` model — a completely separate entity from `Client`. DRF's token auth is
   User-model specific and would require an entirely separate implementation for this
   entity.

5. **The "many eyes" argument applies to cryptographic primitives, not DB lookups.**
   The meaningful cryptographic operations (hashing, Fernet encryption, PBKDF2 derivation)
   are handled by `hashlib` (stdlib) and the `cryptography` package — both extensively
   audited. The custom auth itself is a ~100-line DB lookup + IP check; its attack surface
   is too small for "many eyes" to add meaningful value.

6. **DRF token auth is not a standard.** It uses the same `Authorization: Token <value>`
   HTTP header format as our auth, but the token format and storage are proprietary in
   both implementations. True standards (OAuth2, JWT) are inappropriate for a fleet
   automation platform with static long-lived tokens on controlled hosts.

## Consequences

- Existing clients are unaffected: the data migration hashes tokens in-place; clients
  continue sending the same plaintext bearer token they've always had; the server now
  hashes on lookup.
- `export_clients` and `export_dns_servers` no longer need a `--passphrase` flag — a
  token hash is not a usable credential, so the export file no longer contains sensitive
  material that warrants encryption. The passphrase machinery is removed from export
  commands; `import_*` commands retain it only for backward compatibility with pre-hashing
  export files.
- If a production database is breached, captured token hashes are not directly usable as
  bearer tokens (would require a preimage attack on SHA-256 with 256-bit entropy input —
  computationally infeasible).
- `DNSServer.api_token` follows the identical hashing pattern despite being in the
  `ophix-zones` package — the same rationale applies.

## Follow-up (2026-07-12)

`Client.api_token` and `DNSServer.api_token` were renamed to `token_hash` to match what
they actually store. The field name was never updated when this ADR's decision landed,
and a SHA-256 hash reads as an opaque hex string indistinguishable from a live token at a
glance — the old name gave no visual cue on sight (e.g. in an export JSON file) that the
value could not be used to authenticate. Plain column rename, no data transformation,
no change to the hashing/auth behaviour described above. Breaking change to the
`export_clients`/`import_clients`/`export_dns_servers`/`import_dns_servers` JSON schema
(the `api_token` export key is now `token_hash`) — not a security concern, since (per this
ADR) the exported value was already a hash and not a usable credential either way.
