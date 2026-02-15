#!/bin/bash
set -e

# Determine which service to run based on environment variable
SERVICE="${SERVICE_NAME:-enphase_collector}"

echo "Starting $SERVICE with mDNS support..."
echo "Using host's Avahi daemon via /var/run/dbus and /var/run/avahi-daemon/socket"

if [ "$SERVICE" = "enphase_collector" ]; then
    echo "Testing mDNS resolution..."
    if getent hosts envoy.local > /dev/null 2>&1; then
        echo "✓ mDNS resolution working - envoy.local resolves to $(getent hosts envoy.local | awk '{print $1}')"
    else
        echo "⚠️  mDNS resolution test failed (gateway may not be online yet)"
    fi
    echo ""
    echo "Starting Enphase collector..."
    exec runuser -u app -- python3 /app/enphase_collector.py "$@"

elif [ "$SERVICE" = "jaato_advisor" ]; then
    echo "Starting Jaato Energy Advisor..."
    exec runuser -u app -- python3 -m jaato_advisor "$@"

else
    echo "Error: Unknown service '$SERVICE'"
    echo "Valid services: enphase_collector, jaato_advisor"
    exit 1
fi
