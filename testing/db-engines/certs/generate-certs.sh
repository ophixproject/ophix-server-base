#!/usr/bin/env bash
# Generates a throwaway test CA plus server/client certs for the DB engine
# testing matrix (mariadb, postgres, cockroachdb - plaintext/TLS/mTLS).
#
# Not for real use anywhere - self-signed CA, 10 year expiry, weak-by-design
# defaults are fine here since this only ever talks to localhost containers.

set -euo pipefail
cd "$(dirname "$0")"

SUBJ_CA="/CN=ophix-testing-ca"
DAYS=3650

echo "=== Generating CA ==="
openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -nodes -key ca.key -sha256 -days $DAYS -out ca.crt -subj "$SUBJ_CA"

gen_server_cert() {
    local name="$1"
    local cn="$2"
    echo "=== Generating server cert: $name (CN=$cn) ==="
    mkdir -p "$name"
    openssl genrsa -out "$name/server.key" 4096 2>/dev/null
    openssl req -new -key "$name/server.key" -out "$name/server.csr" -subj "/CN=$cn"
    cat > "$name/server.ext" <<EOF
subjectAltName = DNS:$cn, DNS:localhost, IP:127.0.0.1
EOF
    openssl x509 -req -in "$name/server.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
        -out "$name/server.crt" -days $DAYS -sha256 -extfile "$name/server.ext"
    rm -f "$name/server.csr" "$name/server.ext"
    # mysqld refuses to start if the key is group/other readable
    chmod 600 "$name/server.key"
}

gen_server_cert mariadb mariadb-test
gen_server_cert postgres postgres-test
gen_server_cert mssql mssql

echo "=== Generating client cert (mTLS) ==="
mkdir -p client
openssl genrsa -out client/client.key 4096 2>/dev/null
openssl req -new -key client/client.key -out client/client.csr -subj "/CN=ophix_test_client"
openssl x509 -req -in client/client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out client/client.crt -days $DAYS -sha256
rm -f client/client.csr
chmod 600 client/client.key

echo "=== CockroachDB certs (uses its own cert tooling, not openssl) ==="
mkdir -p cockroachdb/certs cockroachdb/client-certs
docker run --rm \
    -v "$(pwd)/cockroachdb/certs:/certs" \
    -v "$(pwd)/cockroachdb/client-certs:/client-certs" \
    cockroachdb/cockroach:latest-v24.1 \
    cert create-ca --certs-dir=/certs --ca-key=/client-certs/ca.key

docker run --rm \
    -v "$(pwd)/cockroachdb/certs:/certs" \
    -v "$(pwd)/cockroachdb/client-certs:/client-certs" \
    cockroachdb/cockroach:latest-v24.1 \
    cert create-node localhost 127.0.0.1 cockroachdb-tls cockroachdb-mtls \
    --certs-dir=/certs --ca-key=/client-certs/ca.key

docker run --rm \
    -v "$(pwd)/cockroachdb/certs:/certs" \
    -v "$(pwd)/cockroachdb/client-certs:/client-certs" \
    cockroachdb/cockroach:latest-v24.1 \
    cert create-client root --certs-dir=/certs --ca-key=/client-certs/ca.key

docker run --rm \
    -v "$(pwd)/cockroachdb/certs:/certs" \
    -v "$(pwd)/cockroachdb/client-certs:/client-certs" \
    cockroachdb/cockroach:latest-v24.1 \
    cert create-client ophix_test_client --certs-dir=/certs --ca-key=/client-certs/ca.key

echo ""
echo "Done. Certs written under $(pwd)/{mariadb,postgres,cockroachdb,client}/"
