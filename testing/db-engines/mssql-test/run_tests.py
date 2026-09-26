"""
Verifies the documented claim for ophix-server-base's sqlserver DATABASES
wiring: TLS is on by default and validates against the OS certificate trust
store rather than a DB_SSL_CA file path. Three scenarios against the same
server (a self-signed cert, no forced bypass unless stated):

  1. Encrypt=yes, TrustServerCertificate=no, CA NOT in the OS trust store
     -> must FAIL (proves it actually validates, doesn't silently accept
        anything)
  2. Encrypt=yes, TrustServerCertificate=yes
     -> must SUCCEED (the common self-hosted bypass operators would use)
  3. Encrypt=yes, TrustServerCertificate=no, CA ADDED to the OS trust store
     -> must SUCCEED (proves genuine chain validation against the OS trust
        store - the actual documented claim, not just "TLS happens")

Then a real end-to-end `ophix-manage migrate` run in scenario-3 conditions,
as the capstone - not just a raw driver ping.
"""
import os
import subprocess
import sys

import pyodbc

HOST = "mssql,1433"
SA_PASSWORD = "OphixTest123!"
DRIVER = "{ODBC Driver 18 for SQL Server}"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def try_connect(trust_cert):
    conn_str = (
        f"DRIVER={DRIVER};SERVER={HOST};DATABASE=master;UID=sa;PWD={SA_PASSWORD};"
        f"Encrypt=yes;TrustServerCertificate={'yes' if trust_cert else 'no'};"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    conn.close()


# --- Scenario 1: strict validation, CA not yet trusted -> must fail ---
try:
    try_connect(trust_cert=False)
    record("1. Strict validation without trusted CA rejects self-signed cert",
           False, "connection SUCCEEDED - expected a certificate validation failure")
except pyodbc.Error as e:
    record("1. Strict validation without trusted CA rejects self-signed cert",
           True, "connection failed as expected")

# --- Scenario 2: TrustServerCertificate=yes bypass -> must succeed ---
try:
    try_connect(trust_cert=True)
    record("2. TrustServerCertificate=yes bypasses validation", True)
except pyodbc.Error as e:
    record("2. TrustServerCertificate=yes bypasses validation", False, str(e))

# --- Add the test CA to the OS trust store ---
subprocess.run(
    ["cp", "/ca.crt", "/usr/local/share/ca-certificates/ophix-testing-ca.crt"],
    check=True,
)
subprocess.run(["update-ca-certificates"], check=True)

# --- Scenario 3: strict validation, CA now trusted -> must succeed ---
try:
    try_connect(trust_cert=False)
    record("3. Strict validation succeeds once CA is in the OS trust store", True)
except pyodbc.Error as e:
    record("3. Strict validation succeeds once CA is in the OS trust store", False, str(e))

# --- Capstone: create a DB and run a real ophix-manage migrate ---
try:
    conn = pyodbc.connect(
        f"DRIVER={DRIVER};SERVER={HOST};DATABASE=master;UID=sa;PWD={SA_PASSWORD};"
        f"Encrypt=yes;TrustServerCertificate=no;",
        timeout=10, autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("IF DB_ID('ophix_test') IS NULL CREATE DATABASE ophix_test")
    conn.close()

    env = os.environ.copy()
    env.update({
        "DB_ENGINE": "sqlserver",
        "DB_NAME": "ophix_test",
        "DB_USER": "sa",
        "DB_PASSWORD": SA_PASSWORD,
        "DB_HOST": "mssql",
        "DB_PORT": "1433",
        "DB_SQLSERVER_ENCRYPT": "yes",
        "DB_SQLSERVER_TRUST_CERT": "no",
        "DJANGO_SECRET_KEY": "test-secret-key-not-for-real-use",
        "SERVER_NAME": "mssql-harness-test",
        "ALLOWED_HOSTS": "*",
    })
    result = subprocess.run(
        ["ophix-manage", "migrate", "--noinput"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    ok = result.returncode == 0
    detail = "" if ok else (result.stdout[-500:] + result.stderr[-500:])
    record("4. Real Django migrate succeeds (CA trusted, no bypass)", ok, detail)
except Exception as e:
    record("4. Real Django migrate succeeds (CA trusted, no bypass)", False, str(e))

print()
print("=== Summary ===")
all_ok = True
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
    all_ok = all_ok and ok

sys.exit(0 if all_ok else 1)
