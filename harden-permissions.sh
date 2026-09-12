#!/bin/bash
# Harden credential file permissions (owner-only)
set -e
cd "$(dirname "$0")"

echo "=== Hardening credential permissions ==="
[ -d credentials ] && chmod 700 credentials/
chmod 600 credentials/*.json 2>/dev/null || true
[ -f .env ] && chmod 600 .env
chmod 700 logs/ 2>/dev/null || true
chmod 755 refresh.sh
echo "All credential files are now owner-only (600)"
ls -la .env credentials/ 2>/dev/null || true
