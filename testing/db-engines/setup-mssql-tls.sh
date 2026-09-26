#!/usr/bin/env bash
# One-time per fresh mssql container: point mssql.conf at the mounted
# self-signed cert/key and restart sqlservr so it takes effect. The container
# image itself has no env-var TLS config - this is the documented mssql-conf
# path, run post-start since the config file doesn't exist until first boot.
set -euo pipefail

docker compose exec -u root mssql /opt/mssql/bin/mssql-conf set network.tlscert /certs/server.crt
docker compose exec -u root mssql /opt/mssql/bin/mssql-conf set network.tlskey /certs/server.key
docker compose exec -u root mssql /opt/mssql/bin/mssql-conf set network.forceencryption 1

echo "Restarting mssql container to apply TLS config..."
docker compose restart mssql

echo "Waiting for SQL Server to come back up..."
for i in $(seq 1 30); do
    if docker compose exec mssql /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "OphixTest123!" -Q "SELECT 1" >/dev/null 2>&1; then
        echo "SQL Server is back up with TLS configured."
        exit 0
    fi
    sleep 2
done

echo "SQL Server did not come back up in time." >&2
exit 1
