# Observix Packaging (Linux) – Installation, Operations, and Release Guide

This document explains **everything in the `packaging/` directory** and how Observix is installed and operated on Linux using **Option B (lighter): installer script + release binaries**.

It is written for:
- Linux operators (Ubuntu/Debian, but works on most systemd-based distros)
- Engineers building and releasing Observix binaries
- Anyone who needs a repeatable “curl | sudo bash” install flow

---

## What this packaging delivers

Observix on Linux consists of four binaries:

- **`observix`** – main CLI (includes `cp` commands, pipeline mgmt, assignments, etc.)
- **`observix-agent`** – the runtime agent that receives assignments from the Control Plane and runs pipelines
- **`observix-control-plane`** – Control Plane API (agent registration, assignments, pipeline registry)
- **`observix-indexer`** – Indexer/normalizer API used by indexed pipelines (for normalization/profiles)

The packaging approach provides:

- ✅ **Release binaries** published via GitHub Releases
- ✅ **Installer script** (`install.sh`) that downloads latest release assets and installs them
- ✅ **systemd services** so components run in the background and survive reboots
- ✅ **Separate configuration files** (Control Plane config, Indexer config, per-agent config, per-pipeline spec files)
- ✅ Optional helper **`observix-ctl`** for service operations (`start/stop/status/logs`)

---

## Directory layout

```
packaging/
├── config/
│   ├── agent.example.yaml
│   ├── control-plane.yaml
│   ├── indexer.yaml
│   └── pipelines/
│       └── pipeline.example.indexed.json
│
├── systemd/
│   ├── observix-agent@.service
│   ├── observix-control-plane.service
│   └── observix-indexer.service
│
├── install.sh
├── uninstall.sh
├── observix-ctl
└── README.md   (this file)
```

### What each file is for

#### `packaging/config/control-plane.yaml`
Default Control Plane service configuration.
Installed to:
- `/etc/observix/control-plane.yaml`

#### `packaging/config/indexer.yaml`
Default Indexer service configuration.
Installed to:
- `/etc/observix/indexer.yaml`

#### `packaging/config/agent.example.yaml`
Example agent config file.
Installed to:
- `/etc/observix/agents/agent.example.yaml`

Agents are launched as:
- `observix-agent -c /etc/observix/agents/<agent-id>.yaml`

#### `packaging/config/pipelines/pipeline.example.indexed.json`
Example pipeline spec file (JSON). You can use it as a base for creating pipelines via the CLI:
- `observix cp pipelines create --name ... --spec-file ...`

Installed to:
- `/etc/observix/pipelines/pipeline.example.indexed.json`

#### `packaging/systemd/*.service`
systemd unit files for keeping services running in the background.

Installed to:
- `/etc/systemd/system/<unit>.service`

#### `packaging/install.sh`
Linux installer script implementing **Option B**:
- Downloads latest GitHub release binaries
- Installs to `/opt/observix/bin`
- Creates symlinks in `/usr/local/bin`
- Writes configs into `/etc/observix`
- Installs systemd units
- Enables and starts Control Plane + Indexer by default
- Leaves Agent start as opt-in (because each agent needs its own config file)

#### `packaging/uninstall.sh`
Removes Observix from a machine:
- Stops services
- Removes binaries, configs, systemd units (depending on script behavior)
- Reloads systemd daemon

#### `packaging/observix-ctl`
Small helper script to control services:
- `status`, `start`, `stop`, `restart`, `logs`

---

## Linux installation (Option B)

### Supported Linux baseline

This packaging assumes:
- A Linux distro that uses **systemd**
- `curl`, `jq`, `systemctl` available
- Network access to GitHub Releases (or GitHub API)

Tested best on:
- Ubuntu 20.04+
- Debian 11+
- Amazon Linux 2 / 2023 (systemd)
- RHEL/Rocky/Alma 8+ (systemd)

---

## Installation method 1: curl | sudo bash (recommended)

### Install latest release

1) Ensure dependencies are installed:

```bash
sudo apt-get update
sudo apt-get install -y curl jq
```

2) Install Observix (downloads latest GitHub Release assets):

```bash
curl -sSL https://raw.githubusercontent.com/theeghanprojecthub/Observix-Pro-Max/main/packaging/install.sh | sudo bash
```

If the repo is private, pass a GitHub token:

```bash
export GITHUB_TOKEN="ghp_xxx..."
curl -sSL https://raw.githubusercontent.com/theeghanprojecthub/Observix-Pro-Max/main/packaging/install.sh | sudo bash

or

curl -sSL -H "Authorization: token xxxxxxxxxx" https://raw.githubusercontent.com/theeghanprojecthub/Observix-Pro-Max/main/packaging/install.sh | sudo -E bash
```

> The installer uses GitHub’s `releases/latest` API to find the newest tag and download assets.

---

## Installation method 2: install from release bundle (air-gapped friendly)

If you publish a tarball release bundle (recommended), you can install without hitting GitHub raw content.

Typical flow:

1) Download the tarball from Releases:

```bash
curl -L -o observix-linux-amd64.tar.gz <release-asset-url>
tar -xzf observix-linux-amd64.tar.gz
cd observix-linux-amd64
sudo ./install.sh
```

2) Verify binaries exist:

```bash
observix --help
observix-agent --help
observix-control-plane --help
observix-indexer --help
```

---

## Where files are installed on Linux

### Binaries

Installed into:
- `/opt/observix/bin/`

Symlinked into:
- `/usr/local/bin/`

So you can run:
- `observix`
- `observix-agent`
- `observix-control-plane`
- `observix-indexer`

### Configuration

Installed into:
- `/etc/observix/`

Expected structure:

```
/etc/observix/
├── control-plane.yaml
├── indexer.yaml
├── agents/
│   ├── agent.example.yaml
│   ├── agent-a.yaml
│   └── agent-b.yaml
└── pipelines/
    ├── pipeline.example.indexed.json
    └── <your pipeline specs>.json
```

### Data / runtime state

Used directory:
- `/var/lib/observix/`

Logs (optional path if your system wants file logs; systemd logs are in journal):
- `/var/log/observix/`

---

## systemd services

### Control Plane service

Unit:
- `observix-control-plane.service`

Common commands:

```bash
sudo systemctl status observix-control-plane
sudo systemctl start observix-control-plane
sudo systemctl stop observix-control-plane
sudo systemctl restart observix-control-plane
sudo journalctl -u observix-control-plane -f
```

### Indexer service

Unit:
- `observix-indexer.service`

Common commands:

```bash
sudo systemctl status observix-indexer
sudo systemctl start observix-indexer
sudo systemctl stop observix-indexer
sudo systemctl restart observix-indexer
sudo journalctl -u observix-indexer -f
```

### Agent service (templated unit)

Unit template:
- `observix-agent@.service`

Agents run as instances, e.g.:
- `observix-agent@agent-a.service`
- `observix-agent@agent-b.service`

Start/enable an agent:

```bash
sudo systemctl enable --now observix-agent@agent-a
sudo systemctl status observix-agent@agent-a
sudo journalctl -u observix-agent@agent-a -f
```

Stop an agent:

```bash
sudo systemctl stop observix-agent@agent-a
sudo systemctl disable observix-agent@agent-a
```

---

## Helper command: observix-ctl

If installed, you can use:

```bash
observix-ctl --help
observix-ctl status
observix-ctl start control-plane
observix-ctl start indexer
observix-ctl start agent agent-a
observix-ctl logs agent agent-a
```

This is a convenience wrapper around `systemctl` and `journalctl`.

---

## Configuration model (separated files – recommended)

Observix is intentionally configured using **separate config files**:

- Control Plane config: `/etc/observix/control-plane.yaml`
- Indexer config: `/etc/observix/indexer.yaml`
- Agent config: `/etc/observix/agents/<agent-id>.yaml`
- Pipeline specs: stored separately as JSON (used by CLI via `--spec-file`)

This separation is deliberate to keep the CLI flow stable:

- Pipelines are created/updated via:
  - `observix cp pipelines create/update --spec-file <file>`
- Assignments bind pipelines to agents via:
  - `observix cp assignments create --pipeline-id <id>`

Agents do **not** need pipeline definitions in their local config file.

---

## Agent configuration (create a real agent file)

1) Copy the example:

```bash
sudo mkdir -p /etc/observix/agents
sudo cp /etc/observix/agents/agent.example.yaml /etc/observix/agents/agent-a.yaml
```

2) Edit `/etc/observix/agents/agent-a.yaml`:

- Set `agent_id`
- Set `region`
- Set `control_plane.url`

Example:

```yaml
agent_id: agent-a
region: eu-west-1

control_plane:
  url: http://127.0.0.1:7000
```

3) Start the agent:

```bash
sudo systemctl enable --now observix-agent@agent-a
sudo systemctl status observix-agent@agent-a
```

---

## Pipeline management (CLI flow)

### List pipelines

```bash
observix cp pipelines list
```

### Create a pipeline using a spec file

```bash
observix cp pipelines create \
  --name "syslog-5514-to-ec2-13-indexed" \
  --enabled \
  --spec-file /etc/observix/pipelines/pipeline.example.indexed.json
```

### Update an existing pipeline

```bash
observix cp pipelines update \
  --pipeline-id <PIPELINE_ID> \
  --name "syslog-5514-to-ec2-13-indexed" \
  --enabled \
  --spec-file /etc/observix/pipelines/pipeline.example.indexed.json
```

> `--spec-file` is mandatory because the Control Plane update API expects a full updated spec.

### Assign a pipeline to an agent

```bash
observix cp assignments create \
  --agent-id agent-a \
  --region eu-west-1 \
  --pipeline-id <PIPELINE_ID>
```

### Get assignments for an agent

```bash
observix cp assignments get --agent-id agent-a --region eu-west-1
```

---

## Ports and network requirements

Typical defaults (adjust to your configs):

- Control Plane: `7000/tcp`
- Indexer: `7100/tcp`
- Agent sources: depends (e.g., syslog UDP 5514)

If deploying across machines:
- Agents must reach Control Plane URL
- Indexed pipelines must reach Indexer URL (from agent host)

---

## Operational workflow on Linux

### Start everything (single-node)

```bash
sudo systemctl enable --now observix-control-plane
sudo systemctl enable --now observix-indexer

# after creating /etc/observix/agents/agent-a.yaml
sudo systemctl enable --now observix-agent@agent-a
```

### View status

```bash
observix-ctl status
```

or directly:

```bash
systemctl status observix-control-plane
systemctl status observix-indexer
systemctl status observix-agent@agent-a
```

### Tail logs

```bash
journalctl -u observix-control-plane -f
journalctl -u observix-indexer -f
journalctl -u observix-agent@agent-a -f
```

---

## Upgrades

### Upgrade via re-running installer

Because binaries are installed into `/opt/observix/bin` and symlinked, re-running the installer typically upgrades cleanly:

```bash
curl -sSL https://raw.githubusercontent.com/<ORG>/<REPO>/main/packaging/install.sh | sudo bash
sudo systemctl restart observix-control-plane observix-indexer
```

Agents:

```bash
sudo systemctl restart observix-agent@agent-a
```

> Config files are written “only if missing”, so your existing configs are preserved.

---

## Uninstallation

Run:

```bash
sudo bash /path/to/packaging/uninstall.sh
```

After uninstall, verify:

```bash
systemctl status observix-control-plane || true
systemctl status observix-indexer || true
```

---

## GitHub Releases + GitHub Actions build

### What the release should contain

The GitHub Actions workflow should upload **Linux binaries** as release assets, commonly:

- `observix`
- `observix-agent`
- `observix-control-plane`
- `observix-indexer`

Or as a release bundle tarball:

- `observix-linux-amd64.tar.gz`
- `observix-linux-arm64.tar.gz`
- `sha256sums.txt`

### Tag-based release

The workflow triggers on:

- tags: `v*` (e.g., `v0.1.0`)

Example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Then GitHub Actions builds and publishes release assets.

---

## Troubleshooting

### 1) `--help` doesn’t show expected commands
Ensure:
- You are running the packaged binary you expect
- `which observix` points to `/usr/local/bin/observix`
- The CLI module includes Typer commands under `__main__.py`

Check:

```bash
which observix
observix --help
observix cp --help
```

### 2) Control Plane or Indexer won’t start
Check logs:

```bash
journalctl -u observix-control-plane -n 200 --no-pager
journalctl -u observix-indexer -n 200 --no-pager
```

Check config paths match systemd `ExecStart` args.

### 3) Agent is running but receives no pipelines
Confirm assignment exists:

```bash
observix cp assignments get --agent-id agent-a --region eu-west-1
```

Confirm agent config uses correct region and CP URL.

### 4) Indexed pipeline errors
Confirm indexer is running:

```bash
systemctl status observix-indexer
curl -sS http://127.0.0.1:7100/healthz || true
```

Confirm pipeline processor options point to correct indexer URL.

---

## Security notes (recommended defaults)

- Restrict Control Plane listen interface to `127.0.0.1` if running locally only
- If multi-host, run behind firewall/security groups
- Do not set `allow_origins: ["*"]` unless you truly need it and understand implications
- Store sensitive tokens in environment files or vault, not world-readable configs

---

## Appendix: Quick start (copy/paste)

### Single host quick start

```bash
# Install deps
sudo apt-get update
sudo apt-get install -y curl jq

# Install Observix
curl -sSL https://raw.githubusercontent.com/<ORG>/<REPO>/main/packaging/install.sh | sudo bash

# Create an agent config
sudo cp /etc/observix/agents/agent.example.yaml /etc/observix/agents/agent-a.yaml
sudo nano /etc/observix/agents/agent-a.yaml

# Start agent
sudo systemctl enable --now observix-agent@agent-a

# Create pipeline
observix cp pipelines create \
  --name "syslog-5514-to-ec2-13-indexed" \
  --enabled \
  --spec-file /etc/observix/pipelines/pipeline.example.indexed.json

# Assign pipeline to agent
observix cp pipelines list
observix cp assignments create --agent-id agent-a --region eu-west-1 --pipeline-id <PIPELINE_ID>

# Watch agent logs
sudo journalctl -u observix-agent@agent-a -f
```

---

## Project notes

This packaging is designed to:
- Keep CLI commands stable
- Keep configs separated
- Provide a feasible and straightforward Linux operational model

If you extend packaging:
- Add templates to `packaging/config`
- Add/adjust systemd units in `packaging/systemd`
- Keep install/uninstall scripts idempotent and safe by default
