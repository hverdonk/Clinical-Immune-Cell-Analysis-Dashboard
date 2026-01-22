#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8501}"

if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  echo "Dashboard URL:"
  echo "  https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
else
  echo "Dashboard URL:"
  echo "  http://localhost:${PORT}"
fi