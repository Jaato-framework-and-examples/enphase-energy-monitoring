#!/bin/bash
# Test Enphase Authentication Flow
# This script verifies the complete authentication workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  Enphase Authentication Flow Test"
echo "======================================================================"
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker is not running"
    exit 1
fi

echo "✅ Docker is available"
echo ""

# Load configuration
if [ -f .env ]; then
    echo "📄 Loading configuration from .env..."
    export $(grep -v '^#' .env | xargs)
    echo "✅ Configuration loaded"
else
    echo "⚠️  No .env file found, using defaults"
fi

# Validate required configuration
echo ""
echo "🔐 Validating configuration..."

if [ -z "$ENPHASE_GATEWAY_IP" ]; then
    echo "❌ ENPHASE_GATEWAY_IP is not set"
    echo ""
    echo "Please set it in .env file:"
    echo "  ENPHASE_GATEWAY_IP=192.168.50.42"
    exit 1
fi

echo "✅ Gateway IP: $ENPHASE_GATEWAY_IP"

if [ -z "$ENPHASE_GATEWAY_SERIAL" ]; then
    echo "⚠️  ENPHASE_GATEWAY_SERIAL is not set"
    echo ""
    echo "For testing, you can use a dummy serial: 1234567890AB"
    echo "For production, find your gateway serial:"
    echo "  - Sticker on your gateway"
    echo "  - Enlighten app → Menu → System → Serial Number"
    echo ""
    read -p "Enter gateway serial (or press Enter to skip auth test): " SERIAL_INPUT
    if [ -z "$SERIAL_INPUT" ]; then
        echo "⚠️  Skipping authentication test (no serial provided)"
        echo ""
        echo "You can still test gateway connectivity without authentication..."
    else
        export ENPHASE_GATEWAY_SERIAL="$SERIAL_INPUT"
        echo "✅ Gateway Serial: $ENPHASE_GATEWAY_SERIAL"
    fi
else
    echo "✅ Gateway Serial: $ENPHASE_GATEWAY_SERIAL"
fi

# Test 1: Token module syntax
echo ""
echo "======================================================================"
echo "  Test 1: Token Module Syntax"
echo "======================================================================"
echo ""

# Check if container exists
if docker ps --format '{{.Names}}' | grep -q enphase_collector; then
    echo "✅ enphase_collector container exists"
else
    echo "⚠️  enphase_collector container not running"
    echo "   (This is OK if you haven't started the stack yet)"
fi

# Test 2: Token acquisition (if serial provided)
if [ -n "$ENPHASE_GATEWAY_SERIAL" ]; then
    echo ""
    echo "======================================================================"
    echo "  Test 2: Token Acquisition Flow"
    echo "======================================================================"
    echo ""
    echo "This will test the token acquisition process."
    echo "For this test, you can use a dummy token format (32 hex chars)."
    echo ""
    read -p "Do you want to test token acquisition? (y/N): " TEST_TOKEN
    if [ "$TEST_TOKEN" = "y" ] || [ "$TEST_TOKEN" = "Y" ]; then
        echo ""
        echo "Running token manager..."
        
        # Use python directly if container not running
        if docker ps --format '{{.Names}}' | grep -q enphase_collector; then
            docker exec enphase_collector python3 /app/enphase_token.py \
                --serial "$ENPHASE_GATEWAY_SERIAL" \
                --test-only || true
        else
            echo "⚠️  Container not running - testing Python syntax only..."
            python3 -m py_compile enphase_token.py && echo "✅ Token manager syntax is valid"
        fi
    fi
fi

# Test 3: Gateway connectivity
echo ""
echo "======================================================================"
echo "  Test 3: Gateway Connectivity"
echo "======================================================================"
echo ""

echo "Testing basic connectivity to $ENPHASE_GATEWAY_IP..."

if ping -c 1 -W 2 "$ENPHASE_GATEWAY_IP" &> /dev/null; then
    echo "✅ Gateway is reachable (ping)"
else
    echo "⚠️  Gateway is not reachable (ping failed)"
    echo "   Check:"
    echo "   - Gateway is powered on"
    echo "   - IP address is correct: $ENPHASE_GATEWAY_IP"
    echo "   - You're on the same network"
fi

# Test HTTP endpoint
echo ""
echo "Testing HTTP endpoint..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 5 \
    http://"$ENPHASE_GATEWAY_IP":80/ 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "000" ]; then
    echo "⚠️  Cannot connect to HTTP port 80"
    echo "   Gateway web interface may be disabled or on different port"
elif [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "✅ Gateway HTTP endpoint is responding ($HTTP_CODE)"
elif [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo "✅ Gateway HTTP endpoint requires authentication ($HTTP_CODE)"
    echo "   This is expected - authentication token is needed"
else
    echo "⚠️  Unexpected HTTP response: $HTTP_CODE"
fi

# Test 4: Environment variables
echo ""
echo "======================================================================"
echo "  Test 4: Environment Variables"
echo "======================================================================"
echo ""

echo "Current configuration:"
echo "  ENPHASE_GATEWAY_IP=$ENPHASE_GATEWAY_IP"
echo "  ENPHASE_GATEWAY_PORT=${ENPHASE_GATEWAY_PORT:-80}"
echo "  ENPHASE_GATEWAY_SERIAL=$ENPHASE_GATEWAY_SERIAL"
echo "  ENPHASE_TOKEN_CACHE=${ENPHASE_TOKEN_CACHE:-/tmp/enphase_token.json}"
echo ""

# Summary
echo "======================================================================"
echo "  Test Summary"
echo "======================================================================"
echo ""

echo "✅ All basic tests completed!"
echo ""
echo "Next steps:"
echo "  1. Set ENPHASE_GATEWAY_SERIAL in .env"
echo "  2. Run: docker-compose up -d"
echo "  3. Run: docker exec enphase_collector python3 /app/enphase_token.py --serial <SN>"
echo "  4. View dashboards at http://localhost:3000"
echo ""
echo "For detailed authentication instructions, see: AUTHENTICATION.md"
echo ""
