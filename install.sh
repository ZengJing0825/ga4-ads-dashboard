#!/bin/bash
# Install the dashboard auto-refresh launchd agent (macOS)
set -e
cd "$(dirname "$0")"

PROJECT_DIR="$(pwd)"
LABEL="com.example.dashboard-refresh"
PLIST_SRC="$LABEL.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "=== Installing Dashboard Auto-Refresh ==="
echo "Project dir: $PROJECT_DIR"

# 1. Create directories
mkdir -p logs backups

# 2. Harden permissions
echo "[1/4] Hardening file permissions..."
bash harden-permissions.sh

# 3. Remove any old crontab entry pointing at this refresh.sh
echo "[2/4] Removing old crontab entry..."
crontab -l 2>/dev/null | grep -v "$PROJECT_DIR/refresh.sh" | crontab - 2>/dev/null || true
echo "  crontab cleaned"

# 4. Install launchd agent (substitute the project path into the template)
echo "[3/4] Installing launchd agent..."
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "  launchd agent loaded: $PLIST_DST"

# 5. Verify
echo "[4/4] Verifying..."
launchctl list | grep "$LABEL" || echo "  WARNING: Agent not found in launchctl"

echo ""
echo "=== Installation Complete ==="
echo "Schedule: Daily at 09:00 and 14:00 (local time) - edit $PLIST_SRC to change"
echo "Manual run: ./refresh.sh"
echo "Manual trigger: launchctl start $LABEL"
echo "Check health: cat .health | python3 -m json.tool"
echo "View logs: tail -f logs/refresh.log"
echo "Uninstall: launchctl unload $PLIST_DST"
