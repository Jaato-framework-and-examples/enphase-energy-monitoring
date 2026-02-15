# Jaato-Powered Smart Energy Advisor

## Overview

The Jaato Energy Advisor is an intelligent, AI-powered energy optimization system that replaces the Ollama-based advisor with a more sophisticated multi-agent system using the Jaato AI framework.

## Key Features

### 🤖 Multi-Agent Architecture
- **Price Analyst Agent**: Monitors PVPC prices, predicts optimal times, calculates savings
- **Solar Optimizer Agent**: Maximizes self-consumption, optimizes battery usage
- **Appliance Scheduler Agent**: Learns user preferences, schedules flexible loads
- **Coordinator Agent**: Synthesizes recommendations from all agents

### 📊 Real-Time Streaming
- Continuous insights via Jaato event system
- Live agent output streaming
- Dynamic reconnection with automatic recovery

### 🧠 Memory & Learning
- Remembers user preferences over time
- Learns appliance schedules and patterns
- Adapts recommendations based on user feedback

### 🔧 Tool Use
- Query InfluxDB for historical patterns
- Fetch PVPC prices from ESIOS API
- Get weather forecasts for solar prediction
- Calculate optimal schedules and savings

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Jaato Energy Advisor                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Price        │  │ Solar        │  │ Appliance    │      │
│  │ Analyst      │  │ Optimizer    │  │ Scheduler    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                  │
│                  ┌────────▼────────┐                        │
│                  │   Coordinator   │                        │
│                  └────────┬────────┘                        │
│                           │                                  │
│  ┌────────────────────────┼────────────────────────┐        │
│  │                        │                        │        │
│  ▼                        ▼                        ▼        │
│ ┌─────────┐          ┌─────────┐           ┌─────────┐     │
│ │InfluxDB │          │ Jaato   │           │ Memory  │     │
│ │Client   │          │ Server  │           │ System  │     │
│ └─────────┘          └─────────┘           └─────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Install jaato-sdk (already done)
pip install -r requirements.txt
```

### 2. Start Jaato Server

The advisor connects to a Jaato server via Unix socket (Linux/macOS) or named pipe (Windows).

```bash
# Start jaato server (if not already running)
# The advisor will auto-start if needed
```

### 3. Configure Environment

Edit `.env` file:

```bash
# Jaato Configuration
JAATO_SOCKET_PATH=/tmp/jaato.sock

# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token-here
INFLUXDB_ORG=energy_monitoring
INFLUXDB_BUCKET=home_energy

# Advisor Configuration
ADVISOR_INTERVAL_SECONDS=300  # 5 minutes
```

## Usage

### One-Shot Analysis

Run analysis once and exit:

```bash
python src/jaato_advisor.py --analyze-once
```

### Continuous Streaming Mode

Run continuous analysis with automatic updates:

```bash
python src/jaato_advisor.py --interval 300
```

Press `Ctrl+C` to stop.

### Custom Jaato Socket

```bash
python src/jaato_advisor.py --jaato-socket /custom/path/jaato.sock
```

### Custom InfluxDB URL

```bash
python src/jaato_advisor.py --influxdb-url http://influxdb:8086
```

## Agent Configurations

### Price Analyst Agent

**Purpose**: Analyze PVPC electricity prices and predict optimal consumption times.

**Capabilities**:
- Real-time price monitoring from ESIOS API
- Price prediction based on historical patterns
- Cost-benefit analysis for load shifting
- ROI calculations for battery strategies

**Tools**:
- `influxdb_query`: Query historical consumption
- `fetch_pvpc_prices`: Get current PVPC prices
- `calculate_savings`: Compute ROI for load shifting

**Temperature**: 0.6 (more deterministic)

### Solar Optimizer Agent

**Purpose**: Maximize solar self-consumption and optimize battery usage.

**Capabilities**:
- Solar production pattern analysis
- Load-to-solar alignment strategies
- Battery charging/discharging optimization
- Self-consumption ratio improvement

**Tools**:
- `influxdb_query`: Query production data
- `fetch_weather_forecast`: Get solar irradiance forecasts
- `calculate_self_consumption`: Compute self-consumption metrics

**Temperature**: 0.7 (balanced)

### Appliance Scheduler Agent

**Purpose**: Schedule flexible appliances for optimal cost and solar alignment.

**Capabilities**:
- Appliance power consumption profiling
- User behavior and preference learning
- Multi-objective optimization
- Priority-based conflict resolution

**Tools**:
- `influxdb_query`: Query appliance usage patterns
- `fetch_appliance_profile`: Get appliance power specs
- `calculate_optimal_schedule`: Compute best times
- `check_user_preferences`: Access learned preferences

**Temperature**: 0.8 (more creative for scheduling)

## Data Flow

### 1. Context Building

The advisor builds a rich context from multiple sources:

```python
EnergyContext:
  - Current readings (consumption, production, import/export)
  - Price information (current hour, period, €/kWh)
  - Historical patterns (24h hourly data)
  - User preferences (from memory)
```

### 2. Agent Analysis

Each agent receives the context and produces specialized insights:

```
Price Analyst → "Shift dishwasher to 13:00 saves €75/year"
Solar Optimizer → "Increase self-consumption to 55% saves €120/year"
Appliance Scheduler → "EV charging at 00:00-07:00 optimal"
```

### 3. Coordination

The coordinator synthesizes recommendations:

```
Priority 1: Run dishwasher at 13:30-15:30 (solar peak, flat price)
  - Savings: €75/year
  - Effort: Low
  - Confidence: High

Priority 2: Schedule EV charging 00:00-07:00
  - Savings: €180/year
  - Effort: Low
  - Confidence: High

Priority 3: Increase self-consumption ratio
  - Savings: €120/year
  - Effort: Medium
  - Confidence: Medium
```

## Memory System

The advisor learns from user interactions:

### Stored Preferences

- **Appliance Schedules**: When user typically runs devices
- **Flexible Loads**: Which appliances can be shifted
- **Preferred Analysis Times**: When to send notifications
- **Feedback History**: User responses to recommendations

### Example Learning

```
User: "I prefer to run dishwasher in the evening"
Advisor: "I'll remember that. For evening runs, 22:30-00:30 is optimal
         during valley pricing (€0.08 vs €0.22 peak)."
```

## Integration with Existing System

### Replaces Ollama

The jaato advisor completely replaces the Ollama-based system:

**Before (energy_advisor.py)**:
```python
self.llm = ollama.Client()
response = self.llm.generate(model="llama3.2", prompt=prompt)
```

**After (jaato_advisor.py)**:
```python
async for event in self.jaato.send_message(prompt):
    if event.type == EventType.AGENT_OUTPUT:
        logger.info(f"[JAATO] {event.content}")
```

### Compatible with Existing Infrastructure

- ✅ Uses same InfluxDB database
- ✅ Works with existing Grafana dashboards
- ✅ Compatible with docker-compose setup
- ✅ Can run alongside enphase_collector.py

## Advanced Features

### Real-Time Event Streaming

```python
async for event in self.jaato.get_events():
    if event.type == EventType.AGENT_OUTPUT:
        # Stream live insights
        yield event.content
    elif event.type == EventType.PERMISSION_REQUESTED:
        # Handle permission requests
        await self.handle_permission(event)
```

### Multi-Agent Coordination

```python
# Spawn specialized subagents
price_agent = await spawn_subagent(
    profile="price_analyst",
    task="Analyze PVPC prices for next 24h"
)

solar_agent = await spawn_subagent(
    profile="solar_optimizer",
    task="Optimize self-consumption strategy"
)

# Wait for both to complete
price_result = await price_agent.join()
solar_result = await solar_agent.join()

# Coordinate recommendations
coordinated = await coordinator.synthesize([
    price_result, solar_result
])
```

### Tool Use

Agents can use tools to extend their capabilities:

```python
# Agent can query InfluxDB directly
await agent.use_tool(
    "influxdb_query",
    query="SELECT MEAN(consumption) WHERE time > now() - 24h"
)

# Fetch external data
await agent.use_tool(
    "fetch_pvpc_prices",
    date="2025-02-15"
)
```

## Troubleshooting

### Jaato Server Not Running

**Problem**: `Failed to connect to jaato server`

**Solution**:
1. Check if jaato server is running: `ps aux | grep jaato`
2. Start server manually if needed
3. Verify socket path: `ls -la /tmp/jaato.sock`

### InfluxDB Connection Failed

**Problem**: `Failed to fetch current readings`

**Solution**:
1. Verify InfluxDB is running: `docker ps | grep influxdb`
2. Check URL and token in `.env`
3. Test connection: `curl http://localhost:8086/health`

### No Recommendations Generated

**Problem**: Agents return empty results

**Solution**:
1. Check agent logs: `docker logs jaato_server`
2. Verify data is available in InfluxDB
3. Increase agent temperature for more creativity
4. Check agent system prompts for clarity

## Performance

### Resource Usage

- **Memory**: ~100-200 MB (per advisor instance)
- **CPU**: Minimal (I/O bound, waiting for jaato server)
- **Network**: Local socket communication (negligible)

### Latency

- **One-shot analysis**: 5-15 seconds (depends on jaato server)
- **Continuous mode**: Updates every 5 minutes (configurable)
- **Event streaming**: <100ms per event

## Future Enhancements

### Planned Features

- [ ] Web dashboard for real-time recommendations
- [ ] Mobile app notifications
- [ ] Integration with smart home APIs (Home Assistant, Tesla)
- [ ] Automated appliance control (smart plugs)
- [ ] Weather-aware solar forecasting
- [ ] Multi-site support (multiple properties)

### Community Contributions

Contributions welcome! Areas of interest:
- Additional agent profiles (EV specialist, HVAC optimizer)
- New tool integrations (weather APIs, smart home platforms)
- Localization (languages beyond Spanish PVPC)
- Performance optimizations
- Documentation improvements

## License

MIT License - See LICENSE file for details

## Acknowledgments

- **Jaato AI Framework**: Multi-agent orchestration system
- **Enphase Energy**: Gateway API and hardware
- **InfluxDB**: Time-series database
- **ESIOS**: Spanish electricity price data
