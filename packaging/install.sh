#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="theeghanprojecthub/Observix-Pro-Max"

INSTALL_DIR="/opt/observix/bin"
SYMLINK_DIR="/usr/local/bin"

ETC_DIR="/etc/observix"
AGENT_CFG_DIR="${ETC_DIR}/agents"
PIPELINES_DIR="${ETC_DIR}/pipelines"
INDEXER_PROFILES_DIR="${ETC_DIR}/indexer/profiles"

VAR_LIB_DIR="/var/lib/observix"
LOG_DIR="/var/log/observix"

CP_USER="observix"
AGENT_USER="observix"

CP_SERVICE="observix-control-plane.service"
INDEXER_SERVICE="observix-indexer.service"
AGENT_TEMPLATE="observix-agent@.service"

AUTH_HEADER=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: token ${GITHUB_TOKEN}")
fi

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "This installer must be run as root. Use: sudo bash" >&2
    exit 1
  fi
}

need_cmd() {
  local c="$1"
  if ! command -v "$c" >/dev/null 2>&1; then
    echo "Missing dependency: $c" >&2
    exit 1
  fi
}

ensure_jq() {
  if command -v jq >/dev/null 2>&1; then
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing jq..."
    apt-get update -y
    apt-get install -y jq
    return
  fi

  echo "Missing dependency: jq. Install it and re-run." >&2
  exit 1
}

ensure_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found. This installer requires systemd." >&2
    exit 1
  fi
}

ensure_user() {
  local u="$1"
  if ! id -u "$u" >/dev/null 2>&1; then
    useradd --system --shell /usr/sbin/nologin "$u"
  fi
}

mkdirs() {
  mkdir -p "$INSTALL_DIR" "$ETC_DIR" "$AGENT_CFG_DIR" "$PIPELINES_DIR" "$INDEXER_PROFILES_DIR"
  mkdir -p "$VAR_LIB_DIR" "$LOG_DIR"
}

download_latest_release_asset() {
  local asset_name="$1"
  local out_path="$2"

  local api="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"
  echo "Fetching latest release from: ${GITHUB_REPO}"

  local json
  json="$(curl -sSL "${AUTH_HEADER[@]}" "$api")"

  local message
  message="$(echo "$json" | jq -r '.message // empty' || true)"
  if [[ -n "$message" ]]; then
    echo "GitHub API error: $message" >&2
    echo "If this is a private repo, export GITHUB_TOKEN before running the installer." >&2
    exit 1
  fi

  local tag
  tag="$(echo "$json" | jq -r '.tag_name // empty')"
  if [[ -z "$tag" || "$tag" == "null" ]]; then
    echo "Could not determine latest release tag. Is the repo correct and does it have releases?" >&2
    exit 1
  fi

  local url
  url="$(echo "$json" | jq -r --arg n "$asset_name" '.assets[] | select(.name == $n) | .browser_download_url' | head -n 1)"
  if [[ -z "$url" || "$url" == "null" ]]; then
    echo "Asset not found in latest release: $asset_name" >&2
    echo "Expected a release asset named exactly: $asset_name" >&2
    exit 1
  fi

  echo "Downloading ${asset_name} (${tag})"
  curl -sSL -L "${AUTH_HEADER[@]}" -o "$out_path" "$url"
  chmod 755 "$out_path"
}

install_systemd_units() {
  echo "Installing systemd service units..."

  local base_raw="https://raw.githubusercontent.com/${GITHUB_REPO}/main/packaging/systemd"

  curl -sSL -o "/etc/systemd/system/${CP_SERVICE}" "${base_raw}/observix-control-plane.service"
  curl -sSL -o "/etc/systemd/system/${INDEXER_SERVICE}" "${base_raw}/observix-indexer.service"
  curl -sSL -o "/etc/systemd/system/${AGENT_TEMPLATE}" "${base_raw}/observix-agent@.service"

  systemctl daemon-reload
}

write_default_configs_if_missing() {
  echo "Writing default config templates (only if missing)..."

  local raw_cfg="https://raw.githubusercontent.com/${GITHUB_REPO}/main/packaging/config"

  if [[ ! -f "${ETC_DIR}/control-plane.yaml" ]]; then
    curl -sSL -o "${ETC_DIR}/control-plane.yaml" "${raw_cfg}/control-plane.yaml"
  fi

  if [[ ! -f "${ETC_DIR}/indexer.yaml" ]]; then
    curl -sSL -o "${ETC_DIR}/indexer.yaml" "${raw_cfg}/indexer.yaml"
  fi

  if [[ ! -f "${AGENT_CFG_DIR}/agent.example.yaml" ]]; then
    curl -sSL -o "${AGENT_CFG_DIR}/agent.example.yaml" "${raw_cfg}/agent.example.yaml"
  fi

  if [[ ! -f "${PIPELINES_DIR}/pipeline.example.indexed.json" ]]; then
    curl -sSL -o "${PIPELINES_DIR}/pipeline.example.indexed.json" "${raw_cfg}/pipelines/pipeline.example.indexed.json"
  fi
}

permissions() {
  chown -R root:root "$ETC_DIR" || true
  find "$ETC_DIR" -type d -exec chmod 755 {} \; || true
  find "$ETC_DIR" -type f -exec chmod 644 {} \; || true

  chown -R "${CP_USER}:${CP_USER}" "$VAR_LIB_DIR" "$LOG_DIR" || true
}

enable_services() {
  echo "Enabling services..."
  systemctl enable "${CP_SERVICE}"
  systemctl enable "${INDEXER_SERVICE}"

  systemctl restart "${CP_SERVICE}" || true
  systemctl restart "${INDEXER_SERVICE}" || true
}

print_next_steps() {
  cat <<EOF

✅ Observix installed.

Binaries:
  - ${SYMLINK_DIR}/observix
  - ${SYMLINK_DIR}/observix-agent
  - ${SYMLINK_DIR}/observix-control-plane
  - ${SYMLINK_DIR}/observix-indexer

Configs:
  - ${ETC_DIR}/control-plane.yaml
  - ${ETC_DIR}/indexer.yaml
  - ${ETC_DIR}/agents/agent.example.yaml
  - ${ETC_DIR}/pipelines/pipeline.example.indexed.json

Services:
  - systemctl status observix-control-plane
  - systemctl status observix-indexer
  - systemctl enable --now observix-agent@agent-a   (after you create /etc/observix/agents/agent-a.yaml)

Logs:
  - journalctl -u observix-control-plane -f
  - journalctl -u observix-indexer -f
  - journalctl -u observix-agent@agent-a -f

Agent config pattern:
  sudo cp ${ETC_DIR}/agents/agent.example.yaml ${ETC_DIR}/agents/agent-a.yaml
  sudo nano ${ETC_DIR}/agents/agent-a.yaml

Pipeline flow remains unchanged:
  observix cp pipelines create/update ... --spec-file <file>
  observix cp assignments create ... --pipeline-id <id>

EOF
}

main() {
  need_root
  need_cmd curl
  ensure_jq
  ensure_systemd

  ensure_user "$CP_USER"
  ensure_user "$AGENT_USER"
  mkdirs

  download_latest_release_asset "observix" "${INSTALL_DIR}/observix"
  download_latest_release_asset "observix-agent" "${INSTALL_DIR}/observix-agent"
  download_latest_release_asset "observix-control-plane" "${INSTALL_DIR}/observix-control-plane"
  download_latest_release_asset "observix-indexer" "${INSTALL_DIR}/observix-indexer"

  ln -sf "${INSTALL_DIR}/observix" "${SYMLINK_DIR}/observix"
  ln -sf "${INSTALL_DIR}/observix-agent" "${SYMLINK_DIR}/observix-agent"
  ln -sf "${INSTALL_DIR}/observix-control-plane" "${SYMLINK_DIR}/observix-control-plane"
  ln -sf "${INSTALL_DIR}/observix-indexer" "${SYMLINK_DIR}/observix-indexer"

  install_systemd_units
  write_default_configs_if_missing
  permissions
  enable_services
  print_next_steps
}

main "$@"
