# Jaato Advisor - Docker Deployment Guide

## Overview

The Jaato Energy Advisor can run in a Docker container alongside the existing Enphase monitoring stack. This guide covers the complete Docker deployment.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Host                             │
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │ Jaato Server    │         │ Jaato Advisor   │         │
│  │ (running on     │◄────────┤ Container        │         │
│  │  host)          │  Socket │                  │         │
│  │ /tmp/jaato.sock │         │ - Connects via   │         │
│  └──────────────────┘         │   mapped socket  │         │
│                               └──────────────────┘         │
│                                       │                     │
│                                       ▼                     │
│                              ┌──────────────────┐          │
│                              │ Docker Network   │          │
│                              │ energy_monitoring│          │
│                              │ _net             │          │
│                              └──────────────────┘          │
│                                       │                     │
│                        ┌──────────────┼──────────────┐     │
│                        ▼              ▼              ▼     │
│                ┌──────────┐   ┌──────────┐   ┌──────────┐│
│                │InfluxDB  │   │Grafana   │   │Collector ││
│                │Container │   │Container │   │Container ││
│                └──────────┘   └──────────┘   └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Jaato Server on Host

The Jaato server must run on the **host system** (not in a container) because:
- The advisor container needs to communicate via Unix socket
- Socket mapping is more efficient than network communication
- Jaato server should have access to host resources

**Install and start Jaato server:**

```bash
# Install jaato (if not already installed)
pip install jaato-server

# Start jaato server (runs on /tmp/jaato.sock by default)
jaato server

# Verify server is running
ls -la /tmp/jaato.sock
```

### 2. Docker and Docker Compose

```bash
# Verify Docker is installed
docker --version
docker-compose --version
```

## Deployment Steps

### Step 1: Configure Environment

Copy and customize the environment file:

```bash
cd /home/apanoia/Sources/enphase_monitoring
cp .env.example .env
nano .env  # or your preferred editor
```

**Key settings for the advisor:**

```bash
# Jaato Configuration
JAATO_SOCKET_PATH=/tmp/jaato.sock
ADVISOR_INTERVAL_SECONDS=300

# Optional: External API keys (for enhanced features)
ESIOS_TOKEN=your-esios-token-here
OPENWEATHER_API_KEY=your-openweather-key-here
ADVISOR_LATITUDE=40.4168
ADVISOR_LONGITUDE=-3.7038
```

### Step 2: Verify Docker Compose Configuration

The `docker-compose.yml` already includes the advisor service:

```yaml
jaato_advisor:
  build:
    context: ..
    dockerfile: docker/Dockerfile
  container_name: jaato_energy_advisor
  command: python3 -m jaato_advisor --interval 300
  volumes:
    - /tmp/jaato.sock:/tmp/jaato.sock  # Socket mapping (critical!)
    - ../config:/config:ro
    - ../data:/app/data
    - jaato_logs:/var/log/jaato_advisor
  environment:
    - JAATO_SOCKET_PATH=/tmp/jaato.sock
    - INFLUXDB_URL=http://influxdb:8086
    - INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-enphase-monitoring-token}
  restart: unless-stopped
```

**Critical configuration:**
- ✅ `/tmp/jaato.sock:/tmp/jaato.sock` - Maps host socket to container
- ✅ `INFLUXDB_URL=http://influxdb:8086` - Uses Docker network (not localhost)
- ✅ `restart: unless-stopped` - Auto-restart on failure

### Step 3: Start the Stack

```bash
# Start all services
cd docker
docker-compose up -d

# Check service status
docker-compose ps

# Expected output:
# NAME                         STATUS
# energy_monitoring_influxdb   Up
# energy_monitoring_grafana    Up
# enphase_collector            Up
# jaato_energy_advisor         Up  ← New service
```

### Step 4: Verify Advisor is Running

```bash
# Check advisor logs
docker logs -f jaato_energy_advisor

# Look for successful connection:
# [INFO] Connected to jaato server at /tmp/jaato.sock
# [INFO] Starting energy pattern analysis...
# [INFO] Building energy context...
```

### Step 5: Test Advisor Manually

Run a one-shot analysis from within the container:

```bash
# Execute analysis in running container
docker exec -it jaato_energy_advisor python3 -m jaato_advisor --analyze-once

# Or open shell in container
docker exec -it jaato_energy_advisor bash
python3 -m jaato_advisor --analyze-once
```

## Troubleshooting

### Issue 1: "Failed to connect to jaato server"

**Symptoms:**
```
[ERROR] Failed to connect to jaato server: Connection refused
```

**Solutions:**

1. **Check if Jaato server is running on host:**
```bash
ps aux | grep jaato
ls -la /tmp/jaato.sock
```

2. **Start Jaato server if not running:**
```bash
jaato server &
```

3. **Verify socket mapping in docker-compose.yml:**
```yaml
volumes:
  - /tmp/jaato.sock:/tmp/jaato.sock  # Must be present!
```

### Issue 2: "InfluxDB connection failed"

**Symptoms:**
```
[ERROR] Failed to fetch current readings: Connection refused
```

**Solutions:**

1. **Check InfluxDB container is running:**
```bash
docker ps | grep influxdb
```

2. **Verify URL configuration:**
```bash
# Inside container, should be:
# INFLUXDB_URL=http://influxdb:8086
# NOT http://localhost:8086 (that's the host, not container network)
docker exec -it jaato_energy_advisor env | grep INFLUXDB_URL
```

3. **Test connection from container:**
```bash
docker exec -it jaato_energy_advisor curl http://influxdb:8086/health
```

### Issue 3: "No recommendations generated"

**Symptoms:**
```
[WARNING] Could not extract JSON from LLM response
```

**Solutions:**

1. **Check Jaato server logs:**
```bash
# On host, check jaato server output
jaato logs

# Or restart jaato server with debug mode
jaato server --debug
```

2. **Increase advisor logging:**
```bash
# Add to .env:
LOG_LEVEL=DEBUG

# Restart container
docker-compose restart jaato_advisor
```

3. **Verify InfluxDB has data:**
```bash
# Check Grafana dashboards
open http://localhost:3000

# Or query directly
docker exec -it energy_monitoring_influxdb influx \
  'query("SELECT * FROM home_energy")'
```

### Issue 4: Container restarts repeatedly

**Symptoms:**
```
jaato_energy_advisor - Restarting (1) X seconds ago
```

**Solutions:**

1. **Check container logs:**
```bash
docker logs jaato_energy_advisor --tail 100
```

2. **Check container health:**
```bash
docker inspect jaato_energy_advisor | grep -A 10 Health
```

3. **Manually test startup:**
```bash
docker run --rm \
  -v /tmp/jaato.sock:/tmp/jaato.sock \
  -e INFLUXDB_URL=http://influxdb:8086 \
  --network docker_energy_monitoring_net \
  jaato_energy_advisor \
  python3 -m jaato_advisor --analyze-once
```

## Monitoring and Logs

### View Advisor Logs

```bash
# Follow logs in real-time
docker logs -f jaato_energy_advisor

# Last 100 lines
docker logs --tail 100 jaato_energy_advisor

# Logs with timestamps
docker logs -t jaato_energy_advisor
```

### Check Resource Usage

```bash
# Container stats
docker stats jaato_energy_advisor

# Expected:
# CPU: 1-5% (mostly idle)
# Memory: 100-200 MB
# Network: Minimal (local socket + InfluxDB)
```

### Inspect Container

```bash
# Container details
docker inspect jaato_energy_advisor

# Open shell inside container
docker exec -it jaato_energy_advisor bash

# Check environment
docker exec -it jaato_energy_advisor env | grep JAATO

# Test socket connectivity
docker exec -it jaato_energy_advisor ls -la /tmp/jaato.sock
```

## Scaling and Performance

### Adjust Analysis Interval

Edit `.env` or `docker-compose.yml`:

```bash
# More frequent (every 2 minutes)
ADVISOR_INTERVAL_SECONDS=120

# Less frequent (every 10 minutes)
ADVISOR_INTERVAL_SECONDS=600

# Continuous (30 seconds - NOT recommended)
ADVISOR_INTERVAL_SECONDS=30
```

Then restart:
```bash
docker-compose restart jaato_advisor
```

### Resource Limits

Add to `docker-compose.yml` if needed:

```yaml
jaato_advisor:
  # ... other config ...
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 512M
      reservations:
        cpus: '0.25'
        memory: 256M
```

### Multiple Advisor Instances

To run multiple advisors (e.g., for different analysis profiles):

```yaml
jaato_advisor_price:
  <<: *jaato-advisor-base
  container_name: jaato_energy_advisor_price
  command: python3 -m jaato_advisor --profile price-analyst --interval 300

jaato_advisor_solar:
  <<: *jaato-advisor-base
  container_name: jaato_energy_advisor_solar
  command: python3 -m jaato_advisor --profile solar-optimizer --interval 600
```

## Updating the Advisor

### Pull Latest Code

```bash
cd /home/apanoia/Sources/enphase_monitoring
git pull origin main
```

### Rebuild and Restart

```bash
cd docker
docker-compose build jaato_advisor
docker-compose up -d jaato_advisor
```

### View New Version

```bash
docker exec -it jaato_energy_advisor python3 -c \
  "import jaato_advisor; print(jaato_advisor.__version__)"
```

## Backup and Recovery

### Backup Advisor Data

```bash
# Backup logs
docker run --rm -v jaato_logs:/data -v \
  $(pwd)/backup:/backup alpine tar \
  czf /backup/jaato_logs_$(date +%Y%m%d).tar.gz /data

# Backup configuration
cp .env backup/jaato_env_$(date +%Y%m%d).bak
```

### Restore from Backup

```bash
# Restore logs
docker run --rm -v jaato_logs:/data -v \
  $(pwd)/backup:/backup alpine tar \
  xzf /backup/jaato_logs_20250215.tar.gz -C /

# Restore configuration
cp backup/jaato_env_20250215.bak .env
```

## Production Tips

### 1. Use External API Keys

Add to `.env`:
```bash
ESIOS_TOKEN=your-esios-token
OPENWEATHER_API_KEY=your-openweather-key
```

This provides:
- Real PVPC prices (not estimates)
- Weather-aware solar predictions
- Better recommendations

### 2. Configure Alerts

Use Grafana to alert on advisor failures:

```yaml
# Add to docker-compose.yml
alerting:
  rules:
    - alert: AdvisorDown
      expr: up{job="jaato_advisor"} == 0
      for: 5m
      annotations:
        summary: "Jaato Energy Advisor is down"
```

### 3. Log Rotation

Prevent disk space issues:

```yaml
# Add to docker-compose.yml
jaato_advisor:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

### 4. Health Checks

Already configured in docker-compose.yml:

```yaml
healthcheck:
  test: ["CMD", "python3", "-c", "import sys; sys.exit(0)"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Security Considerations

### 1. Socket Permissions

Ensure the socket is readable by the container:

```bash
# On host
sudo chmod 666 /tmp/jaato.sock
```

Or add the container user to the appropriate group.

### 2. API Key Storage

Never commit `.env` with real API keys:

```bash
# Add to .gitignore
.env
.env.local
.env.production

# Use example files
cp .env.example .env
```

### 3. Network Isolation

The advisor uses the internal Docker network, which provides:
- Isolation from external networks
- Secure communication with InfluxDB
- No exposed ports

## Next Steps

1. **Deploy the stack**: `docker-compose up -d`
2. **Verify connection**: `docker logs -f jaato_energy_advisor`
3. **Test analysis**: Run one-shot analysis
4. **Configure alerts**: Set up Grafana alerts
5. **Monitor performance**: Check resource usage

For more information, see:
- [JAATO_ADVISOR.md](JAATO_ADVISOR.md) - Full advisor documentation
- [JAATO_QUICKSTART.md](JAATO_QUICKSTART.md) - Quick reference guide
- [README.md](../README.md) - Main project documentation
