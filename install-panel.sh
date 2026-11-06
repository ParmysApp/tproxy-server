#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo bash install-panel.sh" >&2; exit 1; fi
if [[ ! -f /etc/tproxy-server/config.json || ! -f /etc/tproxy-server/profiles.json ]]; then
  echo "Upstream tproxy-server must be installed first. See README.fa.md." >&2; exit 1
fi
install -d -m 0755 /opt/tproxy-panel
install -m 0644 "$ROOT/panel/app.py" /tmp/proxy-panel-app.py
install -m 0644 "$ROOT/panel/mtproxy-launcher.py" /tmp/mtproxy-launcher.py
install -m 0644 "$ROOT/panel/Vazirmatn.ttf" /opt/tproxy-panel/Vazirmatn.ttf
python3 "$ROOT/panel/install.py"
rm -f /tmp/proxy-panel-app.py /tmp/mtproxy-launcher.py
