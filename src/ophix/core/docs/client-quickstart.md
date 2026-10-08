---
title: Client Quickstart
slug: client-quickstart
order: 20
section: Getting Started
---

Each Ophix domain has a Tier 1 client package that handles authentication, registration, and data retrieval. All clients follow the same bootstrapping pattern.

This page covers the common workflow. Domain-specific commands (e.g. fetching credentials or configurations) are documented in their respective sections.

---
## Register the host 

Before you can register a client, you must first login to the admin UI at {{ server_url }}/admin/ and register the machine you want to run your client on as a host.  It needs a name and an IP address as a minimum (IPv4 and/or IPv6), and optionally a description.  If you skip this step, you will receive a `403 - Unknown host` error when you attempt to register.


## Install the client

Install the client package in its own virtual environment on the client machine. Each client should have its own venv — do not share venvs between clients or with the server.

Ophix detects a virtual environment by checking the running interpreter itself (`sys.prefix`), not by the venv's folder name or which tool created it — `uv`-managed clients work identically to `venv`/`pip`-managed ones, including venv-aware config file resolution and the `venv_name`/`venv_path` reported to the server for fleet visibility.  So, if you have clients for different Ophix servers running in the same folder, you can safely name the venv anything you like to allow you to identify each.  eg. for {{ client_package }}, you might name the venv {{ client_venv }}  For venv maintenance we highly recommend installing venv-cmds.


```bash
python -m venv {{ client_venv }}
source {{ client_venv }}/bin/activate

pip install {{ client_package }} venv-cmds
```

Or, using [uv](https://docs.astral.sh/uv/):

```bash
uv venv {{ client_venv }}
source {{ client_venv }}/bin/activate

uv pip install {{ client_package }} venv-cmds
```

The installed entry point (the cli command you run) matches the package, minus the `ophix-` prefix:

| Package | Command |
| --- | --- |
| `{{ client_package }}` | `{{ client_command }}` |

---

## Bootstrap with quickstart

The `quickstart` command completes all setup steps in one go, first choose a name for your client (visible on the server, must be unique for the host):

```bash
{{ client_command }} quickstart {{ server_url }} my-client-name
```

This does three things in sequence:

1. Saves the server URL to the local env file (`{{ client_env }}`)
2. Downloads the server's CA certificate and saves the path to the env file
3. Registers this client with the server and saves the returned API token

On success you will see something like:

```text
{{ client_command }} quickstart

Created {{ client_env }} with secure permissions (600)
Server URL saved.
Installing CA certificate...
CA certificate saved to: /path/to/ca-cert.pem
{{ client_env }} updated with {{ client_env_prefix }}_CA_CERT=/path/to/ca-cert.pem
Registering client...
Client registered successfully!
Host:           my-host-name
Name:           my-client-name
Deployment ref: my-client-name
Token saved to {{ client_env }}

Quickstart completed successfully.
```

The client is now authenticated and ready to use.

---

## Step-by-step alternative

If you prefer to run each step individually:

```bash
# 1. Set the server URL
{{ client_command }} set server {{ server_url }}

# 2. Download the CA certificate
{{ client_command }} download ca-cert

# 3. Register the client
{{ client_command }} register my-client-name
```

---

## Verify the connection

After bootstrapping, confirm everything is working:

```bash
{{ client_command }} doctor
```

`doctor` checks the local env file, validates permissions, confirms the CA cert exists, and makes a test authenticated request to the server. A healthy client reports:

```text
{{ client_command }} doctor

  ENV file: /path/to/{{ client_env }}
  ENV permissions: OK (600)
  {{ client_env_prefix }}_URL: {{ server_url }}
  {{ client_env_prefix }}_API_TOKEN: present (64 chars)
  {{ client_env_prefix }}_CA_CERT: /path/to/ca-cert.pem
  Version: x.y.z.n
  Python:  3.x.x
  Venv: {{ client_venv }} (/path/to/{{ client_venv }})

Checking server connectivity...
  Authenticated successfully

Client identity:
  Name:                my-client-name
  Deployment ref:      my-client-name
  Venv name:           {{ client_venv }}
  Venv path:           /path/to/{{ client_venv }}
  Last token rotation: None

Doctor checks completed successfully.
```

To see what the server knows about this client:

```bash
{{ client_command }} info
```

For a full list of options available:

```bash
{{ client_command }} --help
```

the `--help` switch can be used on any sub-command also to explain your options

---

## The local env file

Each client stores its configuration in a domain-specific env file in the project root — for `{{ client_package }}`, this is `{{ client_env }}`.

This file contains the server URL, CA cert path, and API token. It is read automatically by the client on every command. Keep it secure — it is equivalent to a password file.

Recommended permissions:

```bash
chmod 600 {{ client_env }}
```

---

## Token rotation

API tokens should be rotated regularly. Rotation is the primary defence against captured tokens (e.g. from backups). A captured token is useless once rotated.

```bash
{{ client_command }} rotate-token
```

This generates a new token, sends it to the server, and (after the server confirms) updates the local env file. The old token is immediately invalidated.

Rotation should be scheduled — for example, as a daily cron job:

```bash
0 3 * * * {{ client_venv }}/bin/{{ client_command }} rotate-token
```

Rotation jobs must be monitored. A silent rotation failure leaves the client with a stale token. Configure alerting so failures are noticed promptly.

### Automated, server-initiated rotation

If {{ cm_link_open }}ophix-client-management{{ cm_link_close }} is installed, rotation doesn't have to rely on a cron job at all. The server can flag a client for rotation — automatically once its token passes an age threshold, or manually from the Status dashboard — and the client picks this up on its *next normal API call*, rotating its own token transparently with no cron job and no operator action required on the client side.

The server can also enforce a **hard lockout**: once a token exceeds a configured maximum age, the client is refused authentication entirely until an operator unlocks it. This protection is always available (`TOKEN_LOCKOUT_DAYS` in `.env`), even without the plugin. With `ophix-client-management` installed, token rotation is easier to control and easy to see at a glance — a dashboard showing token age across the whole fleet, one-click rotation requests, and the self-healing rotation signal described above keeping clients ahead of the lockout threshold automatically.

---

## Granting access to {{ artifact_name_lower }}s

A client can only retrieve {{ artifact_name_lower }}s it is linked to on the server. There are two ways to do this — both live in the same admin UI at {{ server_url }}.

### From the client

1. Go to {{ server_url }} and open **Clients** in the left-hand menu (under Server Core)
2. Select the client you want to grant access to
3. Click the **{{ artifact_name }}s** tab in the right-hand panel
4. Click **Add {{ artifact_name }}** and select the required {{ artifact_name_lower }} from the dropdown

You can add multiple {{ artifact_name_lower }}s this way.

### From the {{ artifact_name_lower }}

1. Go to {{ server_url }} and click **{{ artifact_name }}s** in the left-hand menu
2. Select the {{ artifact_name_lower }} you want to grant access to
3. Click the **Clients** tab in the right-hand panel
4. Click **Add Client** and select the client from the dropdown

You can add multiple clients this way.
