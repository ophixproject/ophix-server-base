#!/usr/bin/env bash
# Runs `ophix-manage migrate` against every (engine, TLS mode) cell in the
# testing matrix, using the smoke-env venv. Reports pass/fail per cell.

set -uo pipefail
cd "$(dirname "$0")"

VENV="./smoke-env"
MANAGE="$VENV/bin/ophix-manage"
ENV_FILE="./.env"
LOG_DIR="./smoke-logs"
mkdir -p "$LOG_DIR"
mkdir -p ./scratch

BASE_ENV='DJANGO_SECRET_KEY=smoke-test-dummy-key-not-for-real-use
DEBUG=True
ALLOWED_HOSTS=*
INSTALL_DIR='"$(pwd)"'/scratch
SERVER_NAME=smoketest
TIME_ZONE=UTC
LANGUAGE_CODE=en-au'

# name|engine|host|port|dbname|user|password|ssl_ca|ssl_cert|ssl_key
CELLS=(
"mariadb-plain|mariadb|127.0.0.1|3305|ophix_test|ophix_test|ophixtest123|||"
"mariadb-tls|mariadb|127.0.0.1|3307|ophix_test|ophix_test|ophixtest123|certs/ca.crt||"
"mariadb-mtls|mariadb|127.0.0.1|3308|ophix_test|ophix_test|ophixtest123|certs/ca.crt|certs/client/client.crt|certs/client/client.key"
"postgres-plain|postgres|127.0.0.1|5431|ophix_test|ophix_test|ophixtest123|||"
"postgres-tls|postgres|127.0.0.1|5433|ophix_test|ophix_test|ophixtest123|certs/ca.crt||"
"postgres-mtls|postgres|127.0.0.1|5434|ophix_test|ophix_test_client||certs/ca.crt|certs/client/client.crt|certs/client/client.key"
"cockroachdb-insecure|cockroachdb|127.0.0.1|26257|ophix_test|root||||"
"cockroachdb-tls|cockroachdb|127.0.0.1|26258|ophix_test|ophix_test|ophixtest123|certs/cockroachdb/certs/ca.crt||"
"cockroachdb-mtls|cockroachdb|127.0.0.1|26259|ophix_test|ophix_test_client||certs/cockroachdb/certs/ca.crt|certs/cockroachdb/certs/client.ophix_test_client.crt|certs/cockroachdb/certs/client.ophix_test_client.key"
)

PASS=0
FAIL=0
FAILED_CELLS=()

for cell in "${CELLS[@]}"; do
    IFS='|' read -r name engine host port dbname user password ssl_ca ssl_cert ssl_key <<< "$cell"

    {
        echo "$BASE_ENV"
        echo "DB_ENGINE=$engine"
        echo "DB_HOST=$host"
        echo "DB_PORT=$port"
        echo "DB_NAME=$dbname"
        echo "DB_USER=$user"
        echo "DB_PASSWORD=$password"
        [[ -n "$ssl_ca" ]] && echo "DB_SSL_CA=$(pwd)/$ssl_ca"
        [[ -n "$ssl_cert" ]] && echo "DB_SSL_CERT=$(pwd)/$ssl_cert"
        [[ -n "$ssl_key" ]] && echo "DB_SSL_KEY=$(pwd)/$ssl_key"
    } > "$ENV_FILE"

    printf "%-24s " "$name"
    if "$MANAGE" migrate --noinput > "$LOG_DIR/$name.log" 2>&1; then
        echo "PASS"
        PASS=$((PASS+1))
    else
        echo "FAIL (see $LOG_DIR/$name.log)"
        FAIL=$((FAIL+1))
        FAILED_CELLS+=("$name")
    fi
done

echo ""
echo "=== $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
    echo "Failed cells: ${FAILED_CELLS[*]}"
    exit 1
fi
