# Observix Pro — Full Technical Documentation (360°)

> **Purpose of this document**
>
> This is a complete technical reference for **Observix Pro** based on the repo structure and the CLI/API flows established in our working sessions (agents → control-plane pipelines/assignments → optional indexer normalization → destination forwarding).
>
> **Accuracy boundary**
>
> I cannot directly read your private Git working tree from here. This document is therefore written to be **operationally complete** for installation, setup, configuration, CLI usage, and the stable API contracts that your tools expose (as demonstrated in your logs and commands).
>
> If you want an additional appendix that is 100% source-grounded down to internal classes/functions, upload the repo as a zip or paste the remaining modules and I will generate a second “implementation appendix”.

---

## Table of contents

1. [What Observix Pro is](#what-observix-pro-is)  
2. [High-level architecture](#high-level-architecture)  
3. [Core components](#core-components)  
4. [End-to-end flows](#end-to-end-flows)  
5. [Repository layout](#repository-layout)  
6. [Installation](#installation)  
   - [Option B: release binaries + systemd (recommended)](#option-b-release-binaries--systemd-recommended)  
   - [Install and uninstall](#install-and-uninstall)  
7. [Linux operations](#linux-operations)  
8. [Local development](#local-development)  
9. [Configuration reference](#configuration-reference)  
   - [Control plane config](#control-plane-config-control-planeyaml)  
   - [Indexer config](#indexer-config-indexeryaml)  
   - [Agent config](#agent-config-agentexampleyaml--agent-idyaml)  
   - [Pipeline spec](#pipeline-spec-json)  
10. [CLI reference](#cli-reference)  
    - [`observix` CLI](#observix-cli)  
    - [`observix-agent` runtime](#observix-agent-runtime)  
    - [Control plane CLI (`observix cp ...`)](#control-plane-cli-observix-cp-)  
11. [FastAPI API reference](#fastapi-api-reference)  
    - [Control plane endpoints](#control-plane-endpoints)  
    - [Indexer endpoints](#indexer-endpoints)  
12. [Release process](#release-process)  
13. [Troubleshooting](#troubleshooting)  
14. [Operational best practices](#operational-best-practices)  
15. [Security considerations](#security-considerations)  
16. [Glossary](#glossary)  

---

## What Observix Pro is

**Observix Pro** is a lightweight, CLI-first platform for **centralized pipeline management** and **distributed log forwarding**.

It consists of:

- **Agents** that collect logs/events from sources (example: syslog UDP), batch them, optionally normalize them via an indexer, and forward to destinations (example: remote syslog UDP).
- A **Control Plane** that stores pipeline definitions, binds pipelines to agents using assignments, and distributes those assignments to agents.
- An optional **Indexer** that normalizes raw log lines into structured event documents according to a parsing profile (example: `json_auto`).
- A unified **CLI** (`observix`) plus component-specific binaries.

**Key design rule (your requirement):**
- **Agent config**, **pipeline config**, and **control plane config** remain separate.
- Pipelines are created/updated and assigned via the **CLI**, not embedded inside agent config files.

---

## High-level architecture

### Logical components

- `observix-control-plane` (FastAPI): stores pipelines + assignments, agents register/poll
- `observix-indexer` (FastAPI): `/v1/normalize` for converting raw logs into structured docs
- `observix-agent`: runs on edge nodes, receives logs, processes, forwards
- `observix` CLI: creates/updates pipelines and assignments in the control plane

### Conceptual data flow

```text
Syslog Sender -> (UDP) -> Observix Agent -> [raw OR indexed] -> Destination (UDP syslog)

Indexed mode inserts the indexer:
Agent -> (HTTP POST /v1/normalize) -> Indexer -> normalized docs -> Agent -> Destination
```

---

## Core components

### Observix Agent

Responsibilities:

- Listen to configured **source** inputs (e.g., syslog UDP on a port).
- Buffer incoming events (bounded by a queue limit).
- Flush events by batch size/time limits.
- Process each batch:
  - `raw`: pass-through forwarding
  - `indexed`: call indexer and convert response into `Event` objects
- Forward processed events to **destination**.
- Record pipeline stats: `recv`, `sent_events`, `sent_batches`, `buffer`, `last_ok`, `last_err`, etc.

### Control Plane

Responsibilities:

- Register and track agents (`agent_id`, `region`, timestamps, status).
- Store pipelines and their versions.
- Store and serve assignments mapping pipelines to agents/regions.
- Provide idempotent read behavior for agents (etag/revision style).

### Indexer

Responsibilities:

- Provide `/v1/normalize` endpoint.
- Apply a profile to parse raw text and output structured docs/events.
- Keep response shape stable to avoid processor breakage.

---

## End-to-end flows

### Flow 1: Raw forwarder

1. Create a pipeline with `processor.mode=raw`.
2. Assign pipeline to an agent.
3. Run agent.
4. Logs sent to destination as syslog lines.

### Flow 2: Indexed forwarder (normalize via indexer)

1. Start indexer service.
2. Create a pipeline with `processor.mode=indexed`, `indexer_url`, `profile`.
3. Assign pipeline to an agent.
4. Run agent.
5. Agent batches logs, sends them to indexer `/v1/normalize`, receives structured docs, forwards them to destination.

---

## Repository layout

Based on your current tree:

```text
observix-pro/
├─ packaging/
│  ├─ config/
│  │  ├─ pipelines/
│  │  │  └─ pipeline.example.indexed.json
│  │  ├─ agent.example.yaml
│  │  ├─ control-plane.yaml
│  │  └─ indexer.yaml
│  ├─ systemd/
│  │  ├─ observix-agent@.service
│  │  ├─ observix-control-plane.service
│  │  └─ observix-indexer.service
│  ├─ install.sh
│  ├─ uninstall.sh
│  ├─ observix-ctl
│  └─ README.md
│
├─ src/
│  ├─ observix_agent/
│  │  ├─ __main__.py
│  │  └─ ...
│  ├─ observix_cli/
│  │  ├─ __main__.py
│  │  ├─ main.py
│  │  └─ ...
│  ├─ observix_control_plane/
│  │  ├─ __main__.py
│  │  └─ ...
│  ├─ observix_indexer/
│  │  ├─ __main__.py
│  │  └─ ...
│  └─ observix_common/
│
├─ Makefile
├─ pyproject.toml
└─ README_*.md
```

---

## Installation

### Option B: release binaries + systemd (recommended)

This is the approach you chose:

- GitHub Actions builds Linux binaries (PyInstaller).
- Release assets are published on tag (e.g., `v0.1.0`).
- Linux users install via a single command:
  - `curl | sudo bash` using `packaging/install.sh`
- systemd manages long-running services (control plane, indexer, agents).

This is a common pattern for infra tools before publishing an apt repository.

### Install and uninstall

#### Install (example)

```bash

curl -sSL -H "Authorization: token xxxxxxxxxx" https://raw.githubusercontent.com/theeghanprojecthub/Observix-Pro-Max/main/packaging/install.sh | sudo -E bash
```

Installer responsibilities (expected):

- Create system user `observix` (no login)
- Install binaries to `/opt/observix/bin` and symlink into `/usr/local/bin`
- Write default configs into `/etc/observix/...` (only if missing)
- Install systemd units into `/etc/systemd/system/`
- Enable and start:
  - `observix-control-plane`
  - `observix-indexer`
- Agents are started per-instance:
  - `observix-agent@agent-a` (after creating `/etc/observix/agent/agent-a.yaml`)

#### Uninstall

```bash
sudo bash /opt/observix/uninstall.sh
```

(Exact path depends on how your uninstall script is written. The packaging folder contains `uninstall.sh` and should remove binaries, configs, and systemd units safely.)

---

## Linux operations

### systemd units

You ship:

- `packaging/systemd/observix-control-plane.service`
- `packaging/systemd/observix-indexer.service`
- `packaging/systemd/observix-agent@.service` (template)

Common commands:

```bash
sudo systemctl status observix-control-plane
sudo systemctl status observix-indexer

sudo systemctl enable --now observix-control-plane
sudo systemctl enable --now observix-indexer
sudo systemctl restart observix-control-plane
sudo systemctl restart observix-indexer
```

### Agent instances

The `@` template supports multiple agents on the same host:

```bash
# create agent config first
sudo cp /etc/observix/agent/agent.example.yaml /etc/observix/agent/agent-a.yaml
sudo nano /etc/observix/agent/agent-a.yaml

# enable and start
sudo systemctl enable --now observix-agent@agent-a

# logs
sudo journalctl -u observix-agent@agent-a -f
```

### observix-ctl helper

`packaging/observix-ctl` is a convenience wrapper around systemctl/journalctl:

```bash
sudo observix-ctl status
sudo observix-ctl start control-plane
sudo observix-ctl stop indexer
sudo observix-ctl restart agent agent-a
sudo observix-ctl logs agent agent-a
```

---

## Local development

### Prereqs

- Python 3.11 recommended
- `pip`, `venv`
- Optional: `jq` (used by installer scripts)
- Optional: `docker` (only if you decide to containerize dev later; not required)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e .

```
### Run initialisation

```aiignore
observix init
```
or
```aiignore
observix init -p ./my-config

```

Given that:

* `config/` will **not** be committed
* users need a way to bootstrap configs
* Linux installer already does implicit init


| Environment       | How config is created       | Init command |
| ----------------- | --------------------------- | ------------ |
| Local development | User runs `observix init`   | ✅ REQUIRED   |
| Linux installer   | `install.sh` writes configs | ❌ Not needed |
| CI / automation   | Config provided explicitly  | ❌ Not needed |

So:

> **`observix init` is a local-development bootstrapper, not a runtime requirement**


`observix init` **does NOT**:

* start services
* create pipelines
* register agents
* talk to the control plane

It only **writes example configs**.

Files it should generate

When run in a repo (or empty directory):

```text
config/
├─ control-plane.yaml
├─ indexer.yaml
├─ agent.example.yaml
└─ pipelines/
   └─ pipeline.example.indexed.json
```

These files are **safe templates**, not active configs.

---


### Run components locally

```bash
# Control plane
observix-control-plane -c config/control-plane.yaml

# Indexer
observix-indexer -c config/indexer.yaml

# Agent
observix-agent -c config/agent.a.yaml
```

---

## Configuration reference

### Control plane config (`control-plane.yaml`)

Packaging default example:

```yaml
host: 0.0.0.0
port: 7000

allow_origins:
  - "*"

agent_offline_threshold_seconds: 20

database_url: "sqlite:////var/lib/observix/control-plane.db"
```

Parameters:

- `host` (string)
  - Bind address. `0.0.0.0` means all interfaces.
  - Use `127.0.0.1` for local-only.
- `port` (int)
  - HTTP port for the control plane server.
- `storage.type` (string)
  - `sqlite` recommended for lightweight installs and demos.
- `storage.path` (string)
  - SQLite db path. Packaging uses `/var/lib/observix/...` for systemd compatibility.

Why packaging is different from dev configs:
- Packaging prioritizes minimal dependencies (no Postgres required).
- You can add an “enterprise DB mode” later without changing the CLI flow.

### Indexer config (`indexer.yaml`)

Typical packaging shape:

```yaml
host: 0.0.0.0
port: 7100
profiles_dir: /etc/observix/indexer/profiles
```

Parameters:

- `host` (string): bind address
- `port` (int): HTTP port
- `profiles_dir` (string): where profile configs live on Linux

### Agent config (`agent.example.yaml` / `agent-<id>.yaml`)

Example:

```yaml
agent_id: agent-a
region: eu-west-1

control_plane:
  url: http://127.0.0.1:7000
```

Parameters:

- `agent_id` (string): unique ID for the agent
- `region` (string): logical region for multi-region scheduling
- `control_plane.url` (string): base URL for control plane

Why agent config does not include pipelines:
- Pipelines are stored centrally and assigned through control plane.
- This keeps the CLI stable and prevents config drift.

### Pipeline spec (JSON)

Example indexed pipeline (as used in your sessions):

```json
{
  "source": {
    "type": "syslog_udp",
    "options": { "host": "127.0.0.1", "port": 5514, "max_queue_size": 50000 }
  },
  "processor": {
    "mode": "indexed",
    "options": {
      "indexer_url": "http://127.0.0.1:7100",
      "profile": "json_auto",
      "timeout_seconds": 3,
      "include_meta": false
    }
  },
  "destination": {
    "type": "syslog_udp",
    "options": {
      "host": "ec2-13-51-86-207.eu-north-1.compute.amazonaws.com",
      "port": 514,
      "pri": 13,
      "appname": "observix-agent-a"
    }
  },
  "batch_max_events": 50,
  "batch_max_seconds": 1.0
}
```

#### `source`

- `source.type`:
  - `syslog_udp`: UDP listener (RFC3164 style framing is fine for most syslog senders)
- `source.options.host`:
  - bind address to listen on
- `source.options.port`:
  - UDP port to receive logs
- `source.options.max_queue_size`:
  - size of in-memory queue buffer

#### `processor`

- `processor.mode`:
  - `raw`: no indexing
  - `indexed`: normalize via indexer
- Indexed options:
  - `indexer_url` (string): base URL to indexer
  - `profile` (string): profile name
  - `timeout_seconds` (float/int): HTTP timeout for indexer calls
  - `include_meta` (bool): include meta in output events (implementation-defined, but intended for preserving extra fields)

#### `destination`

- `destination.type`:
  - `syslog_udp`: UDP sender
- `destination.options.host`:
  - remote destination host
- `destination.options.port`:
  - destination port (often 514)
- `destination.options.pri`:
  - PRI value (facility+severity)
- `destination.options.appname`:
  - syslog appname field

#### batching

- `batch_max_events` (int): flush batch after N events
- `batch_max_seconds` (float): flush after time threshold even if batch not full

---

## CLI reference

### `observix` CLI

General help:

```bash
observix --help
```

The control plane helper group:

```bash
observix cp --help
```

Environment variables:

- `OBSERVIX_CP_URL`: default base URL for CP requests

### `observix-agent` runtime

Start agent using config:

```bash
observix-agent -c config/agent.a.yaml
```

Expected logging:

- agent registration
- assignments applied
- pipeline stats

### Control plane CLI (`observix cp ...`)

These are the stable commands you already built.

#### Health

```bash
observix cp health
observix cp health --url http://127.0.0.1:7000
```

#### Agents list

```bash
observix cp agents
```

#### Pipelines

List:

```bash
observix cp pipelines list
```

Create:

```bash
observix cp pipelines create --name "..." --enabled --spec-file path/to/pipeline.json
```

Update:

```bash
observix cp pipelines update --pipeline-id <id> --name "..." --enabled --spec-file path/to/pipeline.json
```

#### Assignments

Get:

```bash
observix cp assignments get --agent-id agent-a --region eu-west-1
```

Create:

```bash
observix cp assignments create --agent-id agent-a --region eu-west-1 --pipeline-id <pipeline_id>
```

Delete:

```bash
observix cp assignments delete --assignment-id <assignment_id>
```

---

## FastAPI API reference

### Control plane endpoints

Base URL: `http://<host>:7000`

- `GET /healthz`
  - health endpoint used by tooling/monitoring

- `GET /v1/agents`
  - returns list of registered agents

- `GET /v1/pipelines`
  - returns stored pipelines

- `POST /v1/pipelines`
  - create pipeline (name/enabled/spec)

- `PUT /v1/pipelines/{pipeline_id}`
  - update pipeline

- `GET /v1/agents/{agent_id}/assignments?region=<region>`
  - return assignments for a given agent+region

- `POST /v1/assignments`
  - create assignment: binds pipeline to agent+region

- `DELETE /v1/assignments/{assignment_id}`
  - delete assignment

### Indexer endpoints

Base URL: `http://<host>:7100`

- `POST /v1/normalize`

Request:

```json
{"profile":"json_auto","raw":"<string possibly containing \n>"}
```

Response:
- Keep this response stable. Earlier errors came from “expected events, got doc”.  
- Standardize on either:
  - `{"docs":[...]}` or
  - `{"events":[...]}`
and ensure agent processor matches it.

---

## Release process

You provided a GitHub Actions workflow to build and release Linux binaries on tags (`v*`).

### Recommended release steps

1. Create a tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
2. GitHub Actions runs:
   - builds binaries
   - bundles tarballs
   - uploads assets to GitHub release
3. Linux users install via installer which downloads “latest release”.

### Compatibility notes

- If your workflow uploads tarballs (`observix-linux-amd64.tar.gz`), your installer should download and extract them.
- If your installer downloads individual binaries, your workflow must upload those binaries as release assets.
- Pick one approach and freeze it to avoid breakage.

---

## Troubleshooting

### “indexer_response_missing_events_key” / “missing events”

Cause: response shape mismatch between agent indexed processor and indexer API.

Fix: freeze the indexer contract and add a contract test.

### “Event raw field required” (Pydantic validation)

Cause: indexer output docs missing required fields expected by `Event` model.

Fix:
- ensure indexer returns required fields (`raw` at minimum), or
- agent’s `_dict_to_event` should supply fallbacks consistently.

### Agent receives no pipelines

- check assignments exist
- check agent_id/region match exactly

```bash
observix cp assignments get --agent-id agent-a --region eu-west-1
observix cp pipelines list
```

### systemd failures

```bash
sudo systemctl status observix-control-plane -n 200 --no-pager
sudo journalctl -u observix-control-plane -n 200 --no-pager
```

Common issues:
- wrong config path
- permission issues under `/var/lib/observix`
- ports already in use

---

## Operational best practices

- Back up:
  - `/var/lib/observix/control-plane.db`
- Keep agent ports distinct if running multiple local listeners (5514, 5515)
- Use strict naming conventions for pipelines:
  - `syslog-<port>-to-<dest>-<mode>`
- Monitor agent stats and alert on:
  - growing buffer
  - repeated failures
  - `last_ok` becoming stale

---

## Security considerations

- Binding CP/Indexer to `0.0.0.0` exposes them. Use:
  - firewall rules
  - reverse proxy + auth
  - VPN/private network
- Syslog UDP is unauthenticated and lossy.
- Indexer should enforce request size limits and timeouts.

---

## Glossary

- **Agent**: log collector/forwarder
- **Control plane**: central API storing pipelines and assignments
- **Pipeline**: (source → processor → destination) definition stored in CP
- **Assignment**: binding pipeline to agent/region
- **Indexer**: normalization service called by indexed processor
- **Profile**: parsing behavior used by indexer (example `json_auto`)

---

## Appendix: minimal end-to-end example

### 1) Start services locally

```bash
observix-control-plane -c config/control-plane.yaml
observix-indexer -c config/indexer.yaml
```

### 2) Create and assign pipeline

```bash
observix cp pipelines create   --name "syslog-5514-to-ec2-13-indexed"   --enabled   --spec-file config/pipelines/pipeline.example.indexed.json

observix cp pipelines list
# copy pipeline_id

observix cp assignments create   --agent-id agent-a   --region eu-west-1   --pipeline-id <pipeline_id>
```

### 3) Run agent

```bash
observix-agent -c config/agent.a.yaml
```

### 4) Send syslog message

```bash
echo '<13>Feb 07 21:10:29 demo-app demo-app-A: {"event":"payment_attempt","trace_id":"tr-123","amount":10,"currency":"GBP","status":"OK","ts":"2026-02-07T21:10:29Z"}'   | nc -u -w1 127.0.0.1 5514
```
