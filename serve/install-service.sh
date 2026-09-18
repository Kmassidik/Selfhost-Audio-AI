#!/bin/bash
# Make the studio a permanent service that survives reboots.
#   sudo SELFHOSTAUDIO_ROOT=/path/to/selfhostaudioai serve/install-service.sh
# The unit file needs an absolute path, so it is generated from the environment
# rather than committed with a literal one — the rule from docs/WORKSPACE.md.
set -euo pipefail
ROOT="${SELFHOSTAUDIO_ROOT:?set SELFHOSTAUDIO_ROOT}"
cat > /etc/systemd/system/selfhostaudio-studio.service <<UNIT
[Unit]
Description=selfhostaudioai studio (serve/studio.py)
After=network-online.target

[Service]
WorkingDirectory=$ROOT
Environment=SELFHOSTAUDIO_ROOT=$ROOT
ExecStart=/usr/bin/python3 -u $ROOT/serve/studio.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now selfhostaudio-studio
echo "installed · $(systemctl is-active selfhostaudio-studio) · enabled: $(systemctl is-enabled selfhostaudio-studio)"
