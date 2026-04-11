---
title: Client Quickstart
slug: client-quickstart
order: 2
section: Getting Started
---

Each Ophix domain has a Tier 1 client package that handles authentication, registration, and data retrieval. All clients follow the same bootstrapping pattern.

This page covers the common workflow. Domain-specific commands (e.g. fetching credentials or configurations) are documented in their respective sections.

---

## Install the client

Install the appropriate client package in its own virtual environment on the client machine. Each client should have its own venv — do not share venvs between clients or with the server.

```bash
python -m venv venv
source venv/bin/activate

pip install ophix-cred-client     # for the credentials domain
pip install ophix-conf-client     # for the configurations domain
```

The installed entry point matches the package:

| Package | Command |
| --- | --- |
| `ophix-cred-client` | `cred-client` |
| `ophix-conf-client` | `conf-client` |

---

## Bootstrap with quickstart

The `quickstart` command completes all setup steps in one go:

```bash
cred-client quickstart https://your.server.hostname my-client-name
```

This does three things in sequence:

1. Saves the server URL to the local env file (`.cred.env`)
2. Downloads the server's CA certificate and saves the path to the env file
3. Registers this client with the server and saves the returned API token

On success you will see something like:

```text
→ Setting server URL...
→ Downloading CA certificate...
  CA certificate saved to: /path/to/venv/ca-cert.pem
→ Registering client...
  Client registered successfully!
  Host:            192.168.1.10
  Name:            my-client-name
  Token saved to .cred.env
✓ Quickstart completed successfully
```

The client is now authenticated and ready to use.

---

## Step-by-step alternative

If you prefer to run each step individually:

```bash
# 1. Set the server URL
cred-client set server https://your.server.hostname

# 2. Download the CA certificate
cred-client download ca-cert

# 3. Register the client
cred-client register my-client-name
```

---

## Verify the connection

After bootstrapping, confirm everything is working:

```bash
cred-client doctor
```

`doctor` checks the local env file, validates permissions, confirms the CA cert exists, and makes a test authenticated request to the server. A healthy client reports:

```text
✓ Env file:    /path/to/.cred.env
✓ Permissions: 600 (secure)
✓ CREDSERVER_URL = https://your.server.hostname
✓ CREDSERVER_API_TOKEN present (64 chars)
✓ CREDSERVER_CA_CERT = /path/to/ca-cert.pem
✓ Virtualenv:  venv (/path/to/venv)
✓ Authenticated successfully
✓ Doctor checks completed successfully
```

To see what the server knows about this client:

```bash
cred-client info
```

---

## The local env file

Each client stores its configuration in a domain-specific env file in the project root:

| Client | Env file |
| --- | --- |
| `cred-client` | `.cred.env` |
| `conf-client` | `.conf.env` |

This file contains the server URL, CA cert path, and API token. It is read automatically by the client on every command. Keep it secure — it is equivalent to a password file.

Recommended permissions:

```bash
chmod 600 .cred.env
```

---

## Token rotation

API tokens should be rotated regularly. Rotation is the primary defence against captured tokens (e.g. from backups). A captured token is useless once rotated.

```bash
cred-client rotate-token
```

This generates a new token, sends it to the server, and (after the server confirms) updates the local env file. The old token is immediately invalidated.

Rotation should be scheduled — for example, as a daily cron job:

```bash
0 3 * * * /path/to/venv/bin/cred-client rotate-token
```

Rotation jobs must be monitored. A silent rotation failure leaves the client with a stale token. Configure alerting so failures are noticed promptly.

---

## Granting access to artifacts

A client can only retrieve artifacts it has been explicitly linked to by an administrator. After registering a client:

1. Go to **Admin** and navigate to the artifact (credential or configuration)
2. In the **Clients** inline, add the client and set the appropriate permissions
3. The client can now retrieve that artifact

Alternatively, manage links from the **Client** detail page using the domain inline.
