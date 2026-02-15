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
| **Data Collector** | `enphase_collector.py` | Polls gateway, stores to InfluxDB |
| **Energy Advisor** | `energy_advisor.py` | Pattern analysis & recommendations |
| **Docker Stack** | `docker-compose.yml` | All services configured |
| **Dashboards** | `dashboards/*.json` | Grafana visualizations |

---

## 🔧 Key Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Get recommendations
docker exec enphase_collector python3 /app/energy_advisor.py --analyze-once --no-llm

# Stop everything
docker-compose down
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
Energy Advisor (optional intelligence)
```

---

## ✅ Features

### Phase 1: Data Collection (Immediate)
- ✅ Real-time solar production monitoring
- ✅ Grid consumption tracking
- ✅ Export/import visualization
- ✅ Historical trends (hourly, daily, weekly)

### Phase 2: Intelligence Layer (Optional)
- ✅ Peak hour consumption detection
- ✅ Solar alignment analysis
- ✅ Price-aware recommendations (Spanish PVPC)
- ✅ Estimated savings calculations
- ✅ Optional LLM-based deep insights

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
