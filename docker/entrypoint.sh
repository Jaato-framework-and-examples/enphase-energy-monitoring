#!/bin/bash
set -e

echo "Starting Enphase collector with mDNS support..."
echo "Using host's Avahi daemon via /var/run/dbus and /var/run/avahi-daemon/socket"

echo "Testing mDNS resolution..."
if getent hosts envoy.local > /dev/null 2>&1; then
    echo "✓ mDNS resolution working - envoy.local resolves to $(getent hosts envoy.local | awk '{print $1}')"
else
    echo "⚠️  mDNS resolution test failed (gateway may not be online yet)"
fi

echo ""
echo "Starting Enphase collector..."
# Run the Python collector as non-root user
exec runuser -u app -- python3 /app/enphase_collector.py
