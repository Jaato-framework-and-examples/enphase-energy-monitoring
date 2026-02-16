# 🎴 Enphase Energy Monitoring - Quick Reference

## 🚀 Quick Start

**Prerequisites:**
1. Find your Enphase gateway serial number (sticker or Enlighten app)
2. Get authentication token from: https://enlighten.enphaseenergy.com/entrez-auth-token?serial_num=<YOUR_SERIAL>

```bash
cd enphase_monitoring

# Configure gateway
echo "ENPHASE_GATEWAY_IP=192.168.50.42" >> .env
echo "ENPHASE_GATEWAY_SERIAL=1234567890AB" >> .env

# Start services
docker-compose up -d

# Set up authentication token
docker exec enphase_collector python3 /app/enphase_token.py \
  --serial 1234567890AB \
  --gateway-ip 192.168.50.42
```

Then open http://localhost:3000 (admin/admin)

**For detailed authentication instructions:** See [AUTHENTICATION.md](AUTHENTICATION.md)

---

## 📊 Key Files

| File | Purpose |
|------|---------|
| `src/enphase_collector.py` | Main data collection daemon |
| `src/jaato_advisor.py` | AI-powered energy advisor |
| `src/jaato_agents_config.py` | Multi-agent configurations |
| `docker/docker-compose.yml` | Docker services configuration |
| `setup-docker.sh` | Automated setup script |
| `requirements.txt` | Python dependencies |

---

## 🔧 Common Commands

### Start Everything
```bash
docker-compose up -d
```

### Stop Everything
```bash
docker-compose down
```

### View Logs
```bash
# Real-time logs
docker-compose logs -f

# Specific service
docker-compose logs -f enphase_collector
docker-compose logs -f influxdb
docker-compose logs -f grafana
```

### Restart Services
```bash
docker-compose restart enphase_collector
docker-compose restart influxdb
docker-compose restart grafana
```

### Get AI Recommendations
```bash
# View advisor logs
docker logs -f jaato_energy_advisor

# Run one-shot analysis
docker exec jaato_energy_advisor python3 -m jaato_advisor --analyze-once
```

### Test Gateway Connection
```bash
# From container
docker exec enphase_collector python3 /app/enphase_collector.py --test-connection

# From host (if gateway reachable)
curl http://192.168.50.39:80/api/v1/consumption
```

---

## 🏛 URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| InfluxDB | http://localhost:8086 | (default: no auth) |
| Enphase Gateway | http://192.168.50.39:80 | (local network) |

---

## 📊 Troubleshooting

### No Data in Grafana?

1. **Check collector is running:**
   ```bash
   docker-compose ps
   # Should see "Up" for enphase_collector
   ```

2. **Test gateway connection:**
   ```bash
   docker exec enphase_collector python3 /app/enphase_collector.py --test-connection
   ```

3. **Check InfluxDB:**
   ```bash
   docker exec -it influxdb influx
   > use home_energy
   > select * from energy_readings
   ```

### All Containers Starting but No Data?

- **Gateway IP wrong:** Edit `ENPHASE_GATEWAY_IP` in docker-compose.yml
- **API endpoint wrong:** Check Enphase gateway documentation
- **Test from host:** `curl http://192.168.50.39:80/`

### Grafana Won't Start?

```bash
# Check logs
docker-compose logs grafana

# Recreate container
docker-compose rm -f grafana
docker-compose up -d grafana
```

---

## 🎯 InfluxDB Queries

### Last Hour of Data
```sql
SELECT mean("grid_consumption_w"), mean("solar_production_w")
FROM "home_energy"
WHERE time > now() - 1h
GROUP BY time(10s)
```

### Daily Total
```sql
SELECT integral(sum("grid_consumption_w")/1000
FROM "home_energy"
WHERE time > now() - 24h
```

### Peak Hour Consumption
```sql
SELECT mean("grid_consumption_w")
FROM "home_energy"
WHERE time > now() - 24h
  AND (strftime(%H, time) >= 10 AND strftime(%H, time) < 14
GROUP BY time(1h)
```

---

## 🔧 Dashboard URLs

| Dashboard | URL | ID |
|----------|-----|----|
| Home Energy Overview | http://localhost:3000/d/home-energy-overview | Auto-loaded |
| Consumption Patterns | http://localhost:3000/d/consumption-patterns | Auto-loaded |
| Solar Self-Consumption | http://localhost:3000/d/solar-self-consumption | Auto-loaded |

---

## 📊 System Architecture

```
Enphase Gateway (192.168.50.39)
       ↓
Enphase Collector (polls every 10s)
       ↓
InfluxDB (stores time-series)
       ↓
Grafana (visualizations)
       ↓
Energy Advisor (optional intelligence)
```

---

## 🚀 Development

### Add Custom Recommendation Rule

Edit `energy_advisor.py` → `generate_rule_based_recommendations()`:

```python
# Your custom rule
if custom_condition:
    recommendations.append({
        "type": "custom_rule",
        "severity": "high",
        "title": "Your Title",
        "description": "Your explanation",
        "actions": ["action1", "action2"],
        "estimated_savings_eur_per_year": 50.0
    })
```

### Add New Grafana Dashboard

1. Create dashboard in Grafana UI
2. Export as JSON
3. Save to `dashboards/` directory
4. Restart grafana: `docker-compose restart grafana`

### Change Polling Interval

Edit `enphase_collector.py`:

```python
POLL_INTERVAL_SECONDS = 5  # Default: 10
```

Then restart:
```bash
docker-compose restart enphase_collector
```

---

## 📊 Maintenance

### View Disk Usage
```bash
docker system df
```

### Clean Old Data
```bash
# InfluxDB shell (interactive)
docker exec -it influxdb influx

> use home_energy
> delete FROM energy_readings WHERE time < now() - 30d
```

### Backup InfluxDB
```bash
docker exec influxdb influxd backup -d /var/lib/influxdb2/backup
```

---

## 🔐 Security Notes

### For Production Use:

1. **Change passwords** in `docker-compose.yml`:
   - `GF_SECURITY_ADMIN_PASSWORD`
   - `DOCKER_INFLUXDB_INIT_PASSWORD`

2. **Enable InfluxDB authentication**:
   ```yaml
   influxdb:
     environment:
       - INFLUXDB_TOKEN=your-random-token-here
   ```

3. **Restrict Grafana** to localhost:
   ```yaml
   grafana:
     ports: []
     networks:
       - energy_monitoring_net
   ```

4. **Use firewall** to restrict access

---

## 📚 Roadmap

- [x] **Phase 1**: Data collection working
- [x] **Phase 2**: Visualization in Grafana
- [ ] **Phase 3**: Rule-based recommendations
- [ ] **Phase 4**: LLM intelligence
- [ ] **Phase 5**: Appliance automation

---

## � Version

Current: **1.0.0** (2025-02-14)

**Gateway IP:** 192.168.50.39
**Stack:** Docker Compose + InfluxDB 2.7 + Grafana latest
**Optional:** Ollama for LLM features
