#!/bin/bash
#
# Jaato Energy Advisor - Docker Setup Script
#
# This script helps you set up and deploy the Jaato advisor in Docker.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}\n"
}

print_step() {
    echo -e "\n${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Main script
main() {
    print_header "Jaato Energy Advisor - Docker Setup"

    # Step 1: Check prerequisites
    print_step "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "  Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_success "Docker is installed"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        echo "  Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose is installed"

    # Check if .env exists
    if [ ! -f "../.env" ]; then
        print_step "Creating .env from .env.example..."
        cp ../.env.example ../.env
        print_success "Created .env file"
        echo -e "${YELLOW}  Please edit .env and configure your settings${NC}"
    else
        print_success ".env file already exists"
    fi

    # Step 2: Check Jaato server
    print_step "Checking Jaato server..."

    if [ -S "/tmp/jaato.sock" ]; then
        print_success "Jaato server socket found at /tmp/jaato.sock"
    else
        print_error "Jaato server socket not found at /tmp/jaato.sock"
        echo ""
        echo "Please start Jaato server on the host:"
        echo "  ${YELLOW}jaato server${NC}"
        echo ""
        read -p "Press Enter after starting Jaato server, or Ctrl+C to exit..."

        if [ ! -S "/tmp/jaato.sock" ]; then
            print_error "Jaato server still not running. Exiting."
            exit 1
        fi
        print_success "Jaato server is now running"
    fi

    # Step 3: Verify Docker Compose configuration
    print_step "Verifying Docker Compose configuration..."

    if grep -q "jaato_advisor:" docker-compose.yml; then
        print_success "Jaato advisor service found in docker-compose.yml"
    else
        print_error "Jaato advisor service not found in docker-compose.yml"
        print_error "Please ensure you're using the updated docker-compose.yml"
        exit 1
    fi

    # Step 4: Check if InfluxDB is running
    print_step "Checking InfluxDB container..."

    if docker ps | grep -q "energy_monitoring_influxdb"; then
        print_success "InfluxDB container is running"
    else
        echo -e "${YELLOW}  InfluxDB container not running. Starting it now...${NC}"
        docker-compose up -d influxdb
        sleep 5
        print_success "InfluxDB container started"
    fi

    # Step 5: Build advisor image
    print_step "Building Jaato advisor image..."
    docker-compose build jaato_advisor
    print_success "Image built successfully"

    # Step 6: Start advisor container
    print_step "Starting Jaato advisor container..."
    docker-compose up -d jaato_advisor
    print_success "Advisor container started"

    # Step 7: Verify advisor is running
    print_step "Verifying advisor is running..."

    sleep 3

    if docker ps | grep -q "jaato_energy_advisor"; then
        print_success "Advisor container is running"
    else
        print_error "Advisor container failed to start"
        echo ""
        echo "Check logs with:"
        echo "  ${YELLOW}docker logs jaato_energy_advisor${NC}"
        exit 1
    fi

    # Step 8: Test advisor connection
    print_step "Testing advisor connection to Jaato server..."

    if docker exec jaato_energy_advisor ls -la /tmp/jaato.sock &> /dev/null; then
        print_success "Advisor can access Jaato server socket"
    else
        print_error "Advisor cannot access Jaato server socket"
        echo ""
        echo "Check socket mapping in docker-compose.yml:"
        echo "  ${YELLOW}- /tmp/jaato.sock:/tmp/jaato.sock${NC}"
        exit 1
    fi

    # Step 9: Display status
    print_header "Setup Complete!"

    echo ""
    echo "Jaato Energy Advisor is now running in Docker."
    echo ""
    echo "Services:"
    docker ps --filter "name=jaato" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "Useful commands:"
    echo "  ${YELLOW}docker logs -f jaato_energy_advisor${NC}         # View logs"
    echo "  ${YELLOW}docker exec -it jaato_energy_advisor bash${NC}   # Open shell"
    echo "  ${YELLOW}docker-compose restart jaato_advisor${NC}        # Restart advisor"
    echo "  ${YELLOW}docker-compose down${NC}                          # Stop all services"
    echo ""
    echo "Documentation:"
    echo "  ${GREEN}docs/JAATO_DOCKER_DEPLOYMENT.md${NC}              # Docker deployment guide"
    echo "  ${GREEN}docs/JAATO_ADVISOR.md${NC}                        # Full advisor documentation"
    echo "  ${GREEN}docs/JAATO_QUICKSTART.md${NC}                     # Quick reference"
    echo ""
}

# Run main function
main "$@"
