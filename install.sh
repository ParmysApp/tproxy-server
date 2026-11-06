#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash install.sh --hostname proxy.example.com --email you@example.com --site-dir /path/to/site" >&2
  exit 1
fi

hostname=""
email=""
site_dir=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname) hostname="${2:-}"; shift 2 ;;
    --email) email="${2:-}"; shift 2 ;;
    --site-dir) site_dir="${2:-}"; shift 2 ;;
    --help|-h)
      echo "Usage: sudo bash install.sh --hostname proxy.example.com --email you@example.com --site-dir /path/to/site"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$hostname" || -z "$email" || -z "$site_dir" ]]; then
  echo "hostname, email and site-dir are required" >&2
  exit 2
fi
if [[ ! -f "$site_dir/index.html" ]]; then
  echo "Site directory must contain index.html: $site_dir" >&2
  exit 2
fi
for port in 80 443; do
  if ss -H -ltn "( sport = :$port )" | grep -q .; then
    echo "TCP port $port is already in use; refusing to replace another service." >&2
    ss -ltnp "( sport = :$port )" >&2 || true
    exit 1
  fi
done
if systemctl is-active --quiet x-ui.service; then
  echo "x-ui is running; refusing an install that would conflict with its traffic." >&2
  exit 1
fi
bash "$ROOT/deploy/install.sh" --hostname "$hostname" --email "$email" --site-dir "$site_dir"
bash "$ROOT/install-panel.sh"