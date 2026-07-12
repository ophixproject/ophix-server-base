#!/usr/bin/env bash
# CockroachDB secure mode defaults to "cert-password" host-based auth: a
# client presenting a valid client cert authenticates via cert; a client
# presenting no cert falls back to password auth. This lets a single user
# set serve both the "tls" cell (password, no client cert offered) and the
# "mtls" cell (client cert offered) without any custom HBA config - the
# smoke test controls which path is exercised via its own connection params.
set -euo pipefail
cd "$(dirname "$0")"

SQL="
CREATE DATABASE IF NOT EXISTS ophix_test;
CREATE USER IF NOT EXISTS ophix_test WITH PASSWORD 'ophixtest123';
CREATE USER IF NOT EXISTS ophix_test_client;
GRANT ALL ON DATABASE ophix_test TO ophix_test;
GRANT ALL ON DATABASE ophix_test TO ophix_test_client;
"

for svc in cockroachdb-tls cockroachdb-mtls; do
    echo "=== Setting up users on $svc ==="
    docker compose exec -T "$svc" cockroach sql --certs-dir=/certs --host=localhost -e "$SQL"
done
