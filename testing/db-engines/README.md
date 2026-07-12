# DB engine testing matrix

Docker-based test harness validating Ophix against every supported DB engine
in plaintext, TLS, and mutual-TLS modes. Oracle and SQL Server are excluded —
see `ophix-dbengine-oracle`/`ophix-dbengine-mssql` docs for why (Oracle has no
TLS support at all; SQL Server's TLS doesn't use the generic `DB_SSL_*`
mechanism the other engines share).

## Usage

```bash
cd testing/db-engines
bash certs/generate-certs.sh      # one-time: throwaway CA + server/client certs
docker compose up -d
bash setup-cockroach-users.sh        # one-time per fresh cockroach volume
bash setup-postgres-mtls-role.sh     # one-time per fresh postgres-mtls volume
```

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
