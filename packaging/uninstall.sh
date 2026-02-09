#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/observix/bin"
SYMLINK_DIR="/usr/local/bin"

ETC_DIR="/etc/observix"
VAR_LIB_DIR="/var/lib/observix"
LOG_DIR="/var/log/observix"

CP_SERVICE="observix-control-plane.service"
INDEXER_SERVICE="observix-indexer.service"
AGENT_TEMPLATE="observix-agent@.service"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "This uninstaller must be run as root. Use: sudo bash" >&2
    exit 1
  fi
}

main() {
  need_root

  echo "Stopping services..."
  systemctl stop "${CP_SERVICE}" || true
  systemctl stop "${INDEXER_SERVICE}" || true

  # Stop all agent instances if any exist
  systemctl list-units --type=service "observix-agent@*.service" --no-legend 2>/dev/null | awk '{print $1}' | while read -r svc; do
    [[ -n "$svc" ]] && systemctl stop "$svc" || true
  done

  echo "Disabling services..."
  systemctl disable "${CP_SERVICE}" || true
  systemctl disable "${INDEXER_SERVICE}" || true

  systemctl list-unit-files "observix-agent@*.service" --no-legend 2>/dev/null | awk '{print $1}' | while read -r svc; do
    [[ -n "$svc" ]] && systemctl disable "$svc" || true
  done

  echo "Removing systemd unit files..."
  rm -f "/etc/systemd/system/${CP_SERVICE}"
  rm -f "/etc/systemd/system/${INDEXER_SERVICE}"
  rm -f "/etc/systemd/system/${AGENT_TEMPLATE}"

  systemctl daemon-reload

  echo "Removing binaries..."
  rm -f "${SYMLINK_DIR}/observix" \
        "${SYMLINK_DIR}/observix-agent" \
        "${SYMLINK_DIR}/observix-control-plane" \
        "${SYMLINK_DIR}/observix-indexer" || true
  rm -rf "${INSTALL_DIR}" || true

  echo "Removing configs and data..."
  rm -rf "${ETC_DIR}" || true
  rm -rf "${VAR_LIB_DIR}" || true
  rm -rf "${LOG_DIR}" || true

  echo "✅ Observix uninstalled."
}

main "$@"
