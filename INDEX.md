# 🏠 Enphase Energy Monitoring & Intelligence System

Complete system for monitoring Enphase gateway solar production and grid consumption with intelligent recommendations for energy optimization.

---

## 🚀 Quick Start (5 Minutes)

```bash
cd enphase_monitoring
./setup.sh
```

Then open http://localhost:3000 (admin/admin) to see real-time energy graphs!

---

## 📁 Documentation

| File | What It Covers |
|------|-----------------|
| **README.md** | Complete setup & configuration guide |
| **QUICKSTART.md** | Quick reference card (1 page) |
| **SYSTEM.md** | System overview and capabilities |
| **setup.sh** | Automated setup script |

---

## 🏛 Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Data Collector** | `src/enphase_collector.py` | Polls gateway, stores to InfluxDB |
| **AI Advisor** | `src/jaato_advisor.py` | Multi-agent energy optimization |
| **Agent Configs** | `src/jaato_agents_config.py` | Specialized agent configurations |
| **External APIs** | `src/external_apis.py` | ESIOS, Weather integrations |
| **Docker Stack** | `docker/docker-compose.yml` | All services configured |
| **Dashboards** | `dashboards/*.json` | Grafana visualizations |

---

## 🔧 Key Commands

```bash
# Start everything
./setup-docker.sh

# View logs
docker logs -f jaato_energy_advisor

# Get recommendations
docker exec jaato_energy_advisor python3 -m jaato_advisor --analyze-once

# Stop everything
docker compose down
```

---

## 📊 Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin / admin |
| **InfluxDB** | http://localhost:8086 | (default: no auth) |

---

## 🎯 Hardware Requirements

| Hardware | RAM | Works |
|----------|-----|-------|
| Existing PC (Docker) | Shared | ✅ Phase 1 |
| Raspberry Pi 4 | 2-8GB | ✅ Everything |
| Raspberry Pi 5 | 4-8GB | ✅ Everything (faster) |
| NAS (Synology/QNAP) | Shared | ✅ Phase 1 |

---

## 📊 System Architecture

```
Enphase Gateway (192.168.50.39)
       ↓
Enphase Collector (polls every 10s)
       ↓
InfluxDB (time-series database)
       ↓
Grafana (dashboards)
       ↓
Jaato AI Advisor (multi-agent optimization)
       ↓
External APIs (ESIOS, Weather)
```

---

## ✅ Features

### Phase 1: Data Collection (Immediate)
- ✅ Real-time solar production monitoring
- ✅ Grid consumption tracking
- ✅ Export/import visualization
- ✅ Historical trends (hourly, daily, weekly)

### Phase 2: AI Intelligence (Active)
- ✅ Multi-agent energy optimization
- ✅ Real-time price fetching (ESIOS API)
- ✅ Weather integration (solar prediction)
- ✅ Autonomous recommendations
- ✅ Natural language insights

---

## 🚀 Status

**Version:** 1.0.0  
**Date:** 2025-02-14  
**Gateway:** 192.168.50.39  
**Status:** ✅ Production Ready

---

## 📚 Documentation

See detailed guides:
- **README.md** - Complete setup and configuration
- **QUICKSTART.md** - Quick reference card
- **SYSTEM.md** - Full system overview

Start with `./setup.sh` or read README.md for detailed setup!
