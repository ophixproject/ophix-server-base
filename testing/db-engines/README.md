# DB engine testing matrix

Docker-based test harness validating Ophix against every supported DB engine.
MariaDB/Postgres/CockroachDB get a full plaintext/TLS/mutual-TLS matrix (9
cells, 9/9 pass — session 48/49). SQL Server gets a differently-shaped test
(see below) — its ODBC driver negotiates encryption per-connection rather
than needing a separate container per mode, so there's no plaintext/TLS/mTLS
split the way the other three have. Oracle is excluded entirely — no TLS
wiring exists for it at all, and there's no record of it ever connecting to a
real Oracle instance even in plaintext; see `ophix-dbengine-oracle`'s own docs.

## Usage

```bash
cd testing/db-engines
bash certs/generate-certs.sh      # one-time: throwaway CA + server/client certs
docker compose up -d
bash setup-cockroach-users.sh        # one-time per fresh cockroach volume
bash setup-postgres-mtls-role.sh     # one-time per fresh postgres-mtls volume
bash setup-mssql-tls.sh              # one-time per fresh mssql container
```

## SQL Server

`ophix-server-base`'s sqlserver wiring claims TLS is on by default and
validates against the OS certificate trust store rather than a `DB_SSL_CA`
file path (the other three engines' mechanism doesn't apply here at all).
Verified directly (2026-09-26), not just by reading the settings code — build
and run `mssql-test` (`docker compose run --rm mssql-test`) after
`setup-mssql-tls.sh`, which exercises all three real scenarios against the
same server:

1. Strict validation (`Encrypt=yes`, `TrustServerCertificate=no`) with the
   test CA **not** in the OS trust store — must **fail** (proves it actually
   validates, not just "TLS happens").
2. `TrustServerCertificate=yes` — must **succeed** (the common self-hosted
   bypass an operator would actually use).
3. Strict validation **after** adding the test CA to the OS trust store —
   must **succeed** (the actual documented claim).
4. A real `ophix-manage migrate` end-to-end in scenario 3's conditions, as
   the capstone.

All 4 passed. Two real gotchas hit building this, worth knowing before
touching it again:

- **Cert file ownership must match the container's runtime UID (10001,
  `mssql`), not just permission bits** — same class of bug as the Postgres/
  CockroachDB client-cert gotcha from the original harness build. Fix via a
  throwaway root-context container (`docker run --rm -v ...:/certs alpine
  chown 10001:10001 ...`), no host `sudo` needed.
- **The cert's SAN must include whatever hostname the *client* actually
  connects through.** The other three engines' tests always connect via
  `localhost:<mapped-port>` from the host, matching their certs' `DNS:
  localhost` SAN entry. `mssql-test` runs as a separate container on the same
  compose network and connects via the service name (`mssql:1433`) instead —
  so the mssql cert's CN/SAN is `mssql`, not `mssql-test` like the naming
  convention would otherwise suggest. If this ever changes to connect via a
  mapped host port instead, regenerate the cert with a SAN that actually
  matches.
- The container image has no `MSSQL_TLS_*` env vars (unlike some docs
  imply) — `mssql-conf set network.tlscert/tlskey/forceencryption` must be
  run post-boot, then the container restarted; `setup-mssql-tls.sh` does
  this.
- **Stale as of the `ophix-dbengine-mariadb` split**: this note used to say
  the test image needed mysqlclient build deps even for sqlserver-only
  testing, because `ophix-server-base` unconditionally depended on
  `mysqlclient`. That's no longer true — `mysqlclient` now comes from
  installing `ophix-dbengine-mariadb` explicitly, same as every other
  engine's plugin. Only install it in the test image for the mariadb cells.

## Cell → connection settings

| Cell | Host:Port | `.env` settings |
|---|---|---|
| mariadb / plaintext | localhost:3305 | `DB_ENGINE=mariadb`, no `DB_SSL_*` |
| mariadb / TLS | localhost:3307 | `DB_ENGINE=mariadb`, `DB_SSL_CA=certs/ca.crt` |
| mariadb / mTLS | localhost:3308 | as above + `DB_SSL_CERT`/`DB_SSL_KEY=certs/client/client.{crt,key}`, user `ophix_test` |
| postgres / plaintext | localhost:5431 | `DB_ENGINE=postgres`, no `DB_SSL_*` |
| postgres / TLS | localhost:5433 | `DB_ENGINE=postgres`, `DB_SSL_CA=certs/ca.crt` |
| postgres / mTLS | localhost:5434 | as above + `DB_SSL_CERT`/`DB_SSL_KEY=certs/client/client.{crt,key}`, user `ophix_test_client` — Postgres's `clientcert=verify-full` requires the DB role name to match the cert's CN exactly, so this is a separate role from `ophix_test` (created manually, not by `POSTGRES_USER`) |
| cockroachdb / plaintext | localhost:26257 | `DB_ENGINE=cockroachdb`, no `DB_SSL_*`, user `root`, no password |
| cockroachdb / TLS | localhost:26258 | `DB_ENGINE=cockroachdb`, `DB_SSL_CA=certs/cockroachdb/certs/ca.crt`, user `ophix_test` + password, no client cert |
| cockroachdb / mTLS | localhost:26259 | as above + `DB_SSL_CERT`/`DB_SSL_KEY` from `certs/cockroachdb/certs/client.ophix_test_client.{crt,key}`, user `ophix_test_client` |

All plaintext/TLS cells use DB `ophix_test`, user `ophix_test`, password
`ophixtest123` (mariadb/postgres) — throwaway credentials, loopback-bound
ports only.

## Tearing down

```bash
docker compose down -v   # -v also removes the data volumes
```
