#!/bin/bash
# Quick setup script for Enphase Energy Monitoring System
# Now includes Jaato AI Advisor setup

set -e

echo "🔌 Enphase Energy Monitoring System Setup"
echo "=========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed. Install with: curl -sSL https://get.docker.com | sh"
    exit 1
fi

# Check Docker Compose (plugin or standalone)
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "❌ Docker Compose not found. Install with:"
    echo "   sudo apt-get install docker-compose-plugin"
    exit 1
fi

echo "✅ Docker and Docker Compose found ($COMPOSE)"
echo ""

# Check if Enphase gateway is reachable
# NOTE: Skip host test since Docker container has Avahi socket mounted
# The container can resolve .local hostnames even if the host cannot
echo "📡 Gateway connectivity will be tested from inside the container"
echo ""

# Check for Jaato server (optional)
if [ -S "/tmp/jaato.sock" ]; then
    echo "✅ Jaato server detected at /tmp/jaato.sock"
    echo "   → Jaato AI Advisor will be enabled"
    JAATO_AVAILABLE=true
else
    echo "⚠️  Jaato server not found at /tmp/jaato.sock"
    echo "   → Jaato AI Advisor will be skipped (optional feature)"
    echo "   → To enable: Run 'jaato server' before this script"
    JAATO_AVAILABLE=false
fi
echo ""

echo "🏗️ Building and starting containers..."
echo ""

# Create log directories
mkdir -p logs

# Stop and remove existing containers (if any) before starting fresh
cd docker && $COMPOSE down --remove-orphans 2>/dev/null && cd ..

# Always rebuild to pick up code changes, let Docker cache layers for speed
echo "📦 Building and starting services..."
cd docker && $COMPOSE up -d --build && cd ..

echo ""
echo "⏳ Waiting for services to be healthy..."
echo ""

# Wait for InfluxDB
echo "Waiting for InfluxDB (port 8086)..."
timeout 60 bash -c 'until curl -s http://localhost:8086/health &> /dev/null; do sleep 1; done' || {
    echo "⚠️  InfluxDB did not start within 60 seconds"
    echo "Check logs with: $COMPOSE logs influxdb"
    exit 1
}
echo "✅ InfluxDB is ready!"

# Wait for Grafana
echo "Waiting for Grafana (port 3000)..."
timeout 60 bash -c 'until curl -s http://localhost:3000/api/health &> /dev/null; do sleep 1; done' || {
    echo "⚠️  Grafana did not start within 60 seconds"
    echo "Check logs with: $COMPOSE logs grafana"
    exit 1
}
echo "✅ Grafana is ready!"

echo ""
echo "🎯 Testing Enphase collector connection..."
if docker exec enphase_collector python3 /app/enphase_collector.py --test-connection 2>&1 | grep -q "Gateway connection successful"; then
    echo "✅ Collector can reach gateway!"
else
    echo "⚠️  Collector cannot reach gateway. Check:"
    echo "   - Gateway IP: $GATEWAY_IP"
    echo "   - Gateway port: $GATEWAY_PORT"
    echo "   - Test manually: curl --insecure https://$GATEWAY_IP:$GATEWAY_PORT/"
    echo ""
    echo "The system will still start, but collector may have errors."
fi

# Jaato Advisor specific checks
if [ "$JAATO_AVAILABLE" = true ]; then
    echo ""
    echo "🤖 Testing Jaato AI Advisor..."
    sleep 3  # Give advisor time to start
    
    # Check if container exists AND is running (not restarting)
    if docker ps | grep -q "jaato_energy_advisor"; then
        # Check if it's actually healthy (not restarting)
        restart_count=$(docker inspect jaato_energy_advisor --format='{{.RestartCount}}')
        current_status=$(docker inspect jaato_energy_advisor --format='{{.State.Status}}')
        
        if [ "$restart_count" -lt 3 ] && [ "$current_status" = "running" ]; then
            echo "✅ Jaato AI Advisor container is running"
            
            # Test socket connectivity
            if docker exec jaato_energy_advisor ls -la /tmp/jaato.sock &> /dev/null; then
                echo "✅ Advisor can access Jaato server socket"
            else
                echo "⚠️  Advisor cannot access Jaato server socket (permissions issue)"
                echo "   Fix: sudo chmod 666 /tmp/jaato.sock"
            fi
        else
            echo "⚠️  Jaato AI Advisor container is unstable (restart count: $restart_count)"
            echo "   Check logs: docker logs jaato_energy_advisor"
        fi
    else
        echo "⚠️  Jaato AI Advisor container not running"
        echo "   Check logs: docker logs jaato_energy_advisor"
    fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Your Home Energy Monitoring System is Running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Access Points:"
echo "  • Grafana:     http://localhost:3000"
echo "    User: admin / admin"
echo ""
echo "  • InfluxDB:   http://localhost:8086"
echo "    (Advanced - for raw data queries)"
echo ""

if [ "$JAATO_AVAILABLE" = true ]; then
    echo "🤖 Jaato AI Advisor:"
    echo "  • Status: Deployed"
    
    # Check if actually healthy
    if docker ps | grep -q "jaato_energy_advisor"; then
        restart_count=$(docker inspect jaato_energy_advisor --format='{{.RestartCount}}' 2>/dev/null || echo "0")
        if [ "$restart_count" -lt 3 ]; then
            echo "  • Health: Running ✓"
            echo "  • Logs: docker logs -f jaato_energy_advisor"
            echo "  • Test: docker exec jaato_energy_advisor python3 -m jaato_advisor --analyze-once"
        else
            echo "  • Health: Unstable (restart loop) ⚠️"
            echo "  • Logs: docker logs jaato_energy_advisor"
            echo "  • Fix: Check socket permissions (sudo chmod 666 /tmp/jaato.sock)"
        fi
    else
        echo "  • Health: Not running ✗"
        echo "  • Logs: docker logs jaato_energy_advisor"
    fi
    echo ""
fi

echo "📋 Next Steps:"
echo "  1. Open Grafana and explore the dashboards"
echo "  2. Check that data is flowing (real-time graphs)"

if [ "$JAATO_AVAILABLE" = true ]; then
    echo "  3. Try the AI advisor: docker exec jaato_energy_advisor python3 -m jaato_advisor --analyze-once"
    echo "  4. Read: docs/JAATO_DOCKER_DEPLOYMENT.md"
else
    echo "  3. (Optional) Enable Jaato AI Advisor:"
    echo "     - Start Jaato server: jaato server"
    echo "     - Re-run: cd docker && $COMPOSE up -d jaato_advisor"
    echo "     - Read: docs/JAATO_DOCKER_DEPLOYMENT.md"
fi

echo ""
echo "📚 View Logs:"
echo "  $COMPOSE logs -f enphase_collector"
if [ "$JAATO_AVAILABLE" = true ]; then
    echo "  $COMPOSE logs -f jaato_advisor  # AI advisor logs"
fi
echo ""
echo "📚 Stop System:"
echo "  $COMPOSE down"
echo ""
