#!/bin/bash
# Native runner for Windows/macOS/Linux (no Docker)
# Auto-detects platform and runs Enphase collector directly

set -e

echo "🖥️  Running Enphase Collector (Native Mode)"
echo "=========================================="
echo ""

# Detect platform
PLATFORM="$(uname -s)"
echo "Detected platform: $PLATFORM"

case "${PLATFORM}" in
    Linux*)
        echo "Platform: Linux"
        echo "mDNS: Using Python socket + Avahi (requires libnss-mdns OR avahi-daemon)"
        echo ""
        
        # Check if we can resolve envoy.local
        # Use Python's socket.gethostbyname like the actual code does
        if python3 -c "import socket; socket.gethostbyname('envoy.local')" > /dev/null 2>&1; then
            IP=$(python3 -c "import socket; print(socket.gethostbyname('envoy.local'))")
            echo "✓ mDNS working - envoy.local resolves to $IP"
        else
            echo "⚠️  mDNS test failed - envoy.local not resolved"
            echo ""
            echo "Your Linux host needs mDNS support. Choose ONE option:"
            echo ""
            echo "OPTION 1 - Install libnss-mdns (recommended for native Python):"
            echo "  sudo apt-get install libnss-mdns"
            echo ""
            echo "OPTION 2 - Use Docker mode (shares host's Avahi socket):"
            echo "  bash setup-docker.sh"
            echo ""
            echo "OPTION 3 - Configure Avahi with Python bindings:"
            echo "  sudo apt-get install python3-avahi"
            echo ""
            echo "Note: Docker mode already works - use bash setup-docker.sh"
            echo ""
        fi
        
        # Check if Python dependencies are installed
        if ! command -v python3 > /dev/null 2>&1; then
            echo "❌ python3 not found - install with: sudo apt-get install python3"
            echo ""
        fi
        
        if ! command -v pip3 > /dev/null 2>&1; then
            PIP=pip3
        else
            PIP=pip
        fi
        
        # Check if requests is installed
        if ! python3 -c "import requests" > /dev/null 2>&1; then
            echo "⚠️  Installing Python requests library..."
            $PIP install requests
            echo ""
        fi
        
        # Run the collector
        echo "🚀 Starting Enphase collector..."
        echo ""
        
        # Set required environment variables
        export ENPHASE_TOKEN_CACHE="$HOME/.enphase"
        export ENPHASE_GATEWAY_PORT=443
        
        # Check if .env file exists and source it
        if [ -f .env ]; then
            set -a
            source .env
            set +a
        fi
        
        # Run collector
        exec python3 src/enphase_collector.py
        ;;
    
    Darwin*)
        echo "Platform: macOS"
        echo "mDNS: Native Bonjour support (built-in)"
        echo ""
        echo "✅ macOS has built-in Bonjour - no setup needed!"
        echo ""
        
        # Check if Python3 is installed
        if ! command -v python3 > /dev/null 2>&1; then
            echo "❌ python3 not found"
            echo "Install Python 3 from python.org"
            echo ""
            exit 1
        fi
        
        # Check if pip3 is installed
        if ! command -v pip3 > /dev/null 2>&1; then
            PIP=pip3
        else
            PIP=pip
        fi
        
        # Check if requests is installed
        if ! python3 -c "import requests" > /dev/null 2>&1; then
            echo "⚠️  Installing Python requests library..."
            $PIP install requests
            echo ""
        fi
        
        # Run the collector
        echo "🚀 Starting Enphase collector..."
        echo ""
        
        # Set required environment variables
        export ENPHASE_TOKEN_CACHE="$HOME/.enphase"
        export ENPHASE_GATEWAY_PORT=443
        
        # Check if .env file exists and source it
        if [ -f .env ]; then
            set -a
            source .env
            set +a
        fi
        
        # Run collector
        exec python3 src/enphase_collector.py
        ;;
    
    MINGW64*|MSYS_NT*|Windows_NT*)
        echo "Platform: Windows"
        echo "mDNS: Native mDNS client (built-in)"
        echo ""
        echo "✅ Windows has built-in mDNS client - no setup needed!"
        echo ""
        
        # Check if Python is installed
        if ! command -v python > /dev/null 2>&1; then
            echo "❌ Python not found - install from python.org"
            echo ""
            exit 1
        fi
        
        # Check if pip is installed
        if ! command -v pip > /dev/null 2>&1; then
            PIP=pip
        else
            PIP=python -m pip
        fi
        
        # Check if requests is installed
        if ! python -c "import requests" > /dev/null 2>&1; then
            echo "⚠️  Installing Python requests library..."
            $PIP install requests
            echo ""
        fi
        
        # Run the collector
        echo "🚀 Starting Enphase collector..."
        echo ""
        
        # Set required environment variables
        set ENPHASE_TOKEN_CACHE=%USERPROFILE%\.enphase
        set ENPHASE_GATEWAY_PORT=443
        
        # Source .env file if it exists (Windows-compatible)
        if exist .env; then
            # Source .env file - read line by line and export
            while IFS= read -r line; do
                # Skip comments and empty lines
                if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ -n "$line" ]]; then
                    # Export the variable
                    export "$line"
                fi
            done < .env
        fi
        
        # Run collector
        exec python src/enphase_collector.py
        ;;
    
    *)
        echo "❌ Unknown platform: $(uname -s)"
        echo "Supported platforms: Linux, macOS, Windows"
        exit 1
        ;;
esac

echo ""
echo "✅ Native mode works WITHOUT Docker!"
echo "  No containers required - runs directly on host"
echo "  mDNS/Bonjour support built-in to your OS"
echo "  Runs collector as your current user ($USER)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Quick Start:"
echo "  $ bash run-local.sh"
echo ""
echo "🐳 Docker Setup:"
echo "  $ bash setup-docker.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
