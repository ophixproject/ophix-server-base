#!/usr/bin/env bash
# Postgres's `clientcert=verify-full` auth requires the connecting role name
# to exactly match the client certificate's CN. The shared test client cert
# (certs/client/client.crt) has CN=ophix_test_client, so postgres-mtls needs
# a role by that exact name - separate from the `ophix_test` role that
# POSTGRES_USER auto-creates on every postgres-* container.
set -euo pipefail
cd "$(dirname "$0")"

docker compose exec -T postgres-mtls psql -U ophix_test -d ophix_test -c "
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ophix_test_client') THEN
            CREATE ROLE ophix_test_client WITH LOGIN;
        END IF;
    END
    \$\$;
    GRANT ALL PRIVILEGES ON DATABASE ophix_test TO ophix_test_client;
    GRANT ALL ON SCHEMA public TO ophix_test_client;
"
