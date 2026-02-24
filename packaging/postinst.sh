#!/bin/bash
# postinst.sh — post-install hook for .deb packages.
#
# dpkg holds its lock while running this script, so we cannot call apt-get
# directly here.  Instead we launch the real setup script in the background
# (detached from dpkg's process group) and exit immediately.  By the time
# apt-get runs inside setup_linux.sh, dpkg will have released the lock.
#
# The user can also run setup manually at any time:
#   sudo /opt/ResilenceScanReportBuilder/setup_linux.sh

INSTALL_DIR="/opt/ResilenceScanReportBuilder"
SETUP_SCRIPT="$INSTALL_DIR/setup_linux.sh"
LOG="/var/log/resilencescan-setup.log"

chmod +x "$SETUP_SCRIPT" 2>/dev/null || true

echo "[SETUP] Installing R, Quarto, TinyTeX and R packages in the background."
echo "[SETUP] This takes 5–20 minutes. Monitor progress:"
echo "[SETUP]   sudo tail -f $LOG"
echo "[SETUP] If anything is missing at first launch, re-run:"
echo "[SETUP]   sudo $SETUP_SCRIPT"

# Detach completely from dpkg's process group so the background job
# survives dpkg exiting and is immune to SIGHUP.
nohup bash "$SETUP_SCRIPT" >"$LOG" 2>&1 &
disown $! 2>/dev/null || true

exit 0
