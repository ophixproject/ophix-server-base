FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 apt-transport-https ca-certificates \
        build-essential default-libmysqlclient-dev pkg-config \
    && curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyodbc

# Internal dev/test harness, not part of the shipped package. The two pins below
# were installed from the maintainer's own private PyPI mirror at build time and
# won't resolve for anyone else - pypi.internal.ophix.io is not publicly reachable.
# To reproduce this harness yourself, point --extra-index-url/--trusted-host at
# your own package index instead (or drop them and use public PyPI once both
# packages have a public release at or above the pinned versions below).
RUN pip install --no-cache-dir \
    --extra-index-url https://pypi.internal.ophix.io/simple/ \
    --trusted-host pypi.internal.ophix.io \
    "ophix-server-base==2026.8.31.1" "ophix-dbengine-mssql==2026.7.12.1"

WORKDIR /test
COPY mssql-test/run_tests.py .
COPY certs/ca.crt /ca.crt

ENTRYPOINT ["python", "run_tests.py"]
