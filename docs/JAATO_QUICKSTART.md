# Jaato Advisor Quick Reference

## Quick Start

```bash
# 1. Install dependencies (already done)
pip install -r requirements.txt

# 2. Run one-shot analysis
python src/jaato_advisor.py --analyze-once

# 3. Run continuous mode (5-min updates)
python src/jaato_advisor.py --interval 300

# 4. Run tests
python tests/test_jaato_advisor.py
```

## Key Components

### Files

| File | Purpose |
|------|---------|
| `src/jaato_advisor.py` | Main advisor implementation |
| `src/jaato_agents_config.py` | Agent configurations |
| `src/energy_advisor.py` | Old Ollama-based advisor (deprecated) |
| `tests/test_jaato_advisor.py` | Test suite |
| `docs/JAATO_ADVISOR.md` | Full documentation |

### Agents

| Agent | Role | Temperature |
|-------|------|-------------|
| `price_analyst` | PVPC price analysis | 0.6 |
| `solar_optimizer` | Self-consumption optimization | 0.7 |
| `appliance_scheduler` | Smart appliance scheduling | 0.8 |

## CLI Options

```bash
python src/jaato_advisor.py [OPTIONS]

Options:
  --jaato-socket PATH    Path to jaato server socket (default: /tmp/jaato.sock)
  --influxdb-url URL     InfluxDB URL (default: http://localhost:8086)
  --analyze-once         Run once and exit
  --interval SECONDS     Analysis interval for continuous mode (default: 300)
```

## Environment Variables

```bash
# Jaato
JAATO_SOCKET_PATH=/tmp/jaato.sock

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=energy_monitoring
INFLUXDB_BUCKET=home_energy

# Advisor
ADVISOR_INTERVAL_SECONDS=300
```

## Example Output

```
============================================================
ANALYSIS RESULT:
============================================================
{
  "timestamp": "2025-02-15T18:45:00",
  "context": {
    "consumption_w": 1500.0,
    "production_w": 3500.0,
    "price_eur_kwh": 0.15,
    "price_period": "flat"
  },
  "analysis": "## Immediate Actions (Next 24h)\n\n### 1. Run Dishwasher During Solar Peak\n**When:** 13:30-15:30 today\n**Why:** Solar production is at maximum (3.5 kW), flat electricity price (€0.15/kWh)\n**Savings:** €75/year vs evening run at peak price\n**Effort:** Low\n**Confidence:** High\n\n### 2. Schedule EV Charging for Valley Hours\n**When:** 00:00-07:00 tonight\n**Why:** Lowest electricity price (€0.08/kWh vs €0.22 peak)\n**Savings:** €180/year\n**Effort:** Low\n**Confidence:** High\n...",
  "duration_seconds": 8.3
}
```

## Troubleshooting

### "Failed to connect to jaato server"

```bash
# Check if jaato server is running
ps aux | grep jaato

# Start jaato server
jaato server

# Check socket path
ls -la /tmp/jaato.sock
```

### "InfluxDB query failed"

```bash
# Check InfluxDB is running
docker ps | grep influxdb

# Restart InfluxDB
docker-compose restart influxdb

# Verify connection
curl http://localhost:8086/health
```

### "No recommendations generated"

- Check agent logs: `docker logs jaato_server`
- Verify InfluxDB has data: Check Grafana dashboards
- Increase agent temperature for more creativity
- Review agent system prompts in `jaato_agents_config.py`

## Architecture Overview

```
User Request
    ↓
JaatoEnergyAdvisor
    ↓
┌─────────────────────────────────────┐
│  Build Context (InfluxDB + Prices)  │
└─────────────────────────────────────┘
    ↓
Send to Jaato Server
    ↓
┌──────────┬──────────┬──────────┐
│  Price   │  Solar   │Appliance │
│ Analyst  │Optimizer │Scheduler │
└──────────┴──────────┴──────────┘
    ↓
Coordinator Agent
    ↓
Stream Recommendations
    ↓
Display/Store Results
```

## Next Steps

1. **Run the test suite**: `python tests/test_jaato_advisor.py`
2. **Try one-shot analysis**: `python src/jaato_advisor.py --analyze-once`
3. **Read full documentation**: `docs/JAATO_ADVISOR.md`
4. **Customize agents**: Edit `src/jaato_agents_config.py`
5. **Build custom tools**: Extend agent capabilities

## Comparison: Ollama vs Jaato

| Feature | Ollama (old) | Jaato (new) |
|---------|--------------|-------------|
| Model | Local Llama3.2 | Multi-agent system |
| Tools | None | Extensible tool use |
| Memory | None | Persistent memory |
| Streaming | Basic | Advanced event system |
| Coordination | Single agent | Multi-agent planning |
| Reconnection | Manual | Automatic recovery |
| Specialization | Generalist | Specialized profiles |

## Migration from Ollama

```python
# OLD (energy_advisor.py)
self.llm = ollama.Client()
response = self.llm.generate(model="llama3.2", prompt=prompt)

# NEW (jaato_advisor.py)
async for event in self.jaato.send_message(prompt):
    if event.type == EventType.AGENT_OUTPUT:
        yield event.content
```

## Performance Tips

1. **Adjust interval**: Use `--interval 600` for 10-minute updates (less CPU)
2. **Cache context**: Context is cached between analyses
3. **Optimize queries**: Limit InfluxDB time range for faster queries
4. **Agent temperature**: Lower = faster, higher = more creative

## Support

- **Full docs**: `docs/JAATO_ADVISOR.md`
- **Tests**: `tests/test_jaato_advisor.py`
- **Issues**: Report bugs on GitHub
