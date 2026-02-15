# Setup Scripts Interaction Guide

## Overview

The project has **two setup scripts** that work together:

1. **`setup-docker.sh`** (root level) - Main system setup
2. **`docker/setup-jaato-advisor.sh`** - Jaato advisor-specific setup

## Relationship Between Scripts

```
setup-docker.sh (Main)
    │
    ├── Detects if Jaato server is running
    │   └── If YES → Starts jaato_advisor container
    │   └── If NO → Skips jaato_advisor (optional feature)
    │
    ├── Starts Core Services:
    │   ├── InfluxDB (required)
    │   ├── Grafana (required)
    │   └── Enphase Collector (required)
    │
    └── Runs health checks on all services

setup-jaato-advisor.sh (Advisor-Specific)
    │
    ├── Focused only on Jaato advisor setup
    ├── More detailed Jaato-specific checks
    ├── Useful for troubleshooting advisor issues
    └── Can be run independently
```

## Script Comparison

| Feature | setup-docker.sh | setup-jaato-advisor.sh |
|---------|----------------|----------------------|
| **Scope** | Entire system | Jaato advisor only |
| **Required** | Yes, for first-time setup | Optional |
| **Jaato Server Check** | Basic (socket exists) | Detailed (running, accessible) |
| **Services Started** | All services | Jaato advisor only |
| **Health Checks** | Basic connectivity | Deep validation |
| **Use Case** | Full system deployment | Advisor troubleshooting |

## Usage Scenarios

### Scenario 1: First-Time Setup (Complete System)

**Use:** `setup-docker.sh`

```bash
cd /home/apanoia/Sources/enphase_monitoring

# Start Jaato server first (optional, for AI advisor)
jaato server &

# Run main setup (deploys everything)
./setup-docker.sh
```

**What happens:**
1. Checks for Jaato server at `/tmp/jaato.sock`
2. If found: Starts `jaato_advisor` container
3. If not found: Skips advisor (system still works)
4. Starts InfluxDB, Grafana, Collector
5. Runs health checks on all services
6. Displays status and next steps

### Scenario 2: Add Jaato Advisor to Existing System

**Use:** `setup-jaato-advisor.sh` OR manual docker-compose

```bash
# Option A: Use advisor-specific script
cd docker
bash setup-jaato-advisor.sh

# Option B: Use docker-compose directly
cd docker
docker-compose up -d jaato_advisor
```

**What happens:**
1. Verifies Jaato server is running
2. Builds advisor image
3. Starts advisor container
4. Tests socket connectivity
5. Verifies InfluxDB connection

### Scenario 3: Troubleshoot Jaato Advisor Issues

**Use:** `setup-jaato-advisor.sh`

```bash
cd docker
bash setup-jaato-advisor.sh
```

**Why this script:**
- More detailed Jaato-specific checks
- Better error messages for advisor issues
- Focused on advisor connectivity only

### Scenario 4: Restart/Update System

**Use:** `setup-docker.sh`

```bash
cd /home/apanoia/Sources/enphase_monitoring
./setup-docker.sh
```

**What happens:**
- Stops all containers
- Rebuilds images (picks up code changes)
- Starts all services
- Runs health checks

## Decision Flow: Which Script to Use?

```
Need to deploy?
    │
    ├─ First time setup?
    │   └─→ Use: setup-docker.sh
    │
    ├─ Already have core system, want to add AI advisor?
    │   └─→ Use: setup-jaato-advisor.sh
    │       OR: docker-compose up -d jaato_advisor
    │
    ├─ Having advisor issues?
    │   └─→ Use: setup-jaato-advisor.sh (detailed checks)
    │
    └─ Updating entire system?
        └─→ Use: setup-docker.sh (rebuilds everything)
```

## Key Differences

### setup-docker.sh

**Pros:**
- ✅ One-stop shop for entire system
- ✅ Handles Jaato server detection gracefully
- ✅ Starts all services in correct order
- ✅ Comprehensive health checks

**Cons:**
- ❌ Less detailed Jaato-specific validation
- ❌ Rebuilds all services (slower)

**Best for:** Initial deployment, full system restarts

### setup-jaato-advisor.sh

**Pros:**
- ✅ Focused on Jaato advisor only
- ✅ More detailed validation
- ✅ Faster (only builds advisor)
- ✅ Better error messages for advisor issues

**Cons:**
- ❌ Requires manual Jaato server start
- ❌ Doesn't touch other services

**Best for:** Adding advisor to existing system, troubleshooting

## Example Workflows

### Workflow 1: Fresh Installation

```bash
# 1. Clone repository
git clone <repo>
cd enphase_monitoring

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Start Jaato server (optional)
jaato server &

# 4. Run main setup
./setup-docker.sh

# 5. Verify everything is running
docker ps
```

### Workflow 2: Add Advisor Later

```bash
# 1. System already running (InfluxDB, Grafana, Collector)
docker ps
# Shows: influxdb, grafana, enphase_collector

# 2. Decide to add AI advisor
jaato server &

# 3. Use advisor-specific setup
cd docker
bash setup-jaato-advisor.sh

# 4. Verify advisor is running
docker ps | grep jaato
```

### Workflow 3: Troubleshoot Advisor

```bash
# Advisor not working properly

# 1. Check advisor logs
docker logs jaato_energy_advisor

# 2. Run detailed advisor setup/check
cd docker
bash setup-jaato-advisor.sh

# 3. Script will identify specific issues
# 4. Fix issues based on script output
```

### Workflow 4: Update System

```bash
# Pull latest code
git pull origin main

# Rebuild and restart everything
./setup-docker.sh

# This rebuilds all services including advisor
```

## Jaato Server Detection Logic

### setup-docker.sh

```bash
if [ -S "/tmp/jaato.sock" ]; then
    echo "✅ Jaato server detected"
    JAATO_AVAILABLE=true
    # Advisor will be started
else
    echo "⚠️  Jaato server not found"
    JAATO_AVAILABLE=false
    # Advisor will be skipped (not an error)
fi
```

**Behavior:**
- Socket exists → Start advisor
- Socket missing → Skip advisor (continue normally)

### setup-jaato-advisor.sh

```bash
if [ -S "/tmp/jaato.sock" ]; then
    echo "✅ Jaato server socket found"
else
    echo "❌ Jaato server socket not found"
    echo "Please start Jaato server first"
    exit 1  # Stops here - requires Jaato server
fi
```

**Behavior:**
- Socket exists → Continue setup
- Socket missing → Stop and show error

## Health Checks Comparison

### setup-docker.sh (Basic)

```bash
# Jaato advisor check
if docker ps | grep -q "jaato_energy_advisor"; then
    echo "✅ Jaato AI Advisor container is running"
    if docker exec jaato_energy_advisor ls -la /tmp/jaato.sock; then
        echo "✅ Advisor can connect to Jaato server"
    fi
fi
```

### setup-jaato-advisor.sh (Detailed)

```bash
# Step 1: Check Jaato server
if [ ! -S "/tmp/jaato.sock" ]; then
    print_error "Jaato server socket not found"
    exit 1
fi

# Step 2: Verify container can access socket
if docker exec jaato_energy_advisor ls -la /tmp/jaato.sock; then
    print_success "Socket accessible from container"
else
    print_error "Socket not accessible"
    exit 1
fi

# Step 3: Test InfluxDB connectivity
docker exec jaato_energy_advisor curl http://influxdb:8086/health

# Step 4: Run one-shot analysis
docker exec jaato_energy_advisor python3 -m jaato_advisor --analyze-once
```

## Recommendations

### For New Users

1. **First time:** Use `setup-docker.sh`
2. **With Jaato:** Start `jaato server` first, then run setup
3. **Without Jaato:** Run setup directly (advisor skipped)

### For Existing Users

1. **Adding Jaato:** Use `setup-jaato-advisor.sh`
2. **Updating:** Use `setup-docker.sh`
3. **Troubleshooting:** Use `setup-jaato-advisor.sh`

### For Development

1. **Quick testing:** Use `docker-compose` commands directly
2. **Full rebuild:** Use `setup-docker.sh`
3. **Advisor testing:** Use `setup-jaato-advisor.sh`

## Summary

- **`setup-docker.sh`** = Main system setup (use this first)
- **`setup-jaato-advisor.sh`** = Advisor-specific setup (use for troubleshooting)
- Both scripts can be used independently or together
- Jaato advisor is **optional** - system works without it
- Scripts gracefully handle missing Jaato server

The scripts are designed to work together seamlessly, with the main script handling the full system and the advisor script providing focused, detailed validation for the Jaato advisor component.
