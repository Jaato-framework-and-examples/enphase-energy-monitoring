# Jaato Advisor Tools - Complete Guide

## Overview

The Jaato Energy Advisor has **4 specialized tools** that allow AI agents to interact with external systems and perform calculations. These tools bridge the gap between the AI agents and real-world data sources.

---

## Tool Architecture

```
Jaato Agent (e.g., Price Analyst)
    │
    │ "I need to know tomorrow's electricity prices"
    │
    ▼
Tool: fetch_pvpc_prices()
    │
    ├─ Calls ESIOS API (Spanish electricity grid)
    ├─ Returns: {0: 0.08, 1: 0.08, ..., 23: 0.22}
    │
    ▼
Agent uses data to make recommendations
    │
    ▼
"Run dishwasher at 13:00 (€0.15/kWh) instead of 20:00 (€0.22/kWh)"
```

---

## Tool #1: fetch_pvpc_prices()

### Purpose
Fetches real-time electricity prices from the Spanish grid (PVPC tariff).

### What It Does

1. **Calls ESIOS API** (Spanish electricity grid operator)
2. **Gets hourly prices** for a specific date
3. **Returns 24 prices** (one per hour) in €/kWh
4. **Falls back to estimates** if API unavailable

### Input Parameters

```python
date: datetime  # Date to fetch prices for (default: today)
```

### Output

```python
{
    0: 0.080,   # 00:00 - €0.08/kWh (valley)
    1: 0.080,   # 01:00 - €0.08/kWh (valley)
    ...
    10: 0.220,  # 10:00 - €0.22/kWh (peak)
    11: 0.220,  # 11:00 - €0.22/kWh (peak)
    ...
    14: 0.150,  # 14:00 - €0.15/kWh (flat)
    ...
    23: 0.150   # 23:00 - €0.15/kWh (flat)
}
```

### Example Usage

```python
# Agent says: "What are electricity prices for tomorrow?"
prices = fetch_pvpc_prices(date=datetime(2025, 2, 16))

# Agent uses this to find optimal times:
# - Valley hours (00:00-08:00): €0.08/kWh → Best for EV charging
# - Flat hours (08:00-10:00, 14:00-18:00): €0.15/kWh → Good for appliances
# - Peak hours (10:00-14:00, 18:00-22:00): €0.22/kWh → Avoid if possible
```

### Configuration

Requires optional ESIOS API token in `.env`:

```bash
ESIOS_TOKEN=your-esios-token-here
```

**Get free token:** https://www.esios.ree.es/en

### Graceful Degradation

If API unavailable (no token, network error):
- Falls back to **estimated prices** based on PVPC 2.0 TD tariff
- System continues working without interruption
- Recommendations still accurate (uses standard rates)

---

## Tool #2: fetch_weather_forecast()

### Purpose
Fetches weather forecasts to predict solar panel production.

### What It Does

1. **Calls OpenWeatherMap API**
2. **Gets weather conditions** for next N hours
3. **Calculates solar potential** (0-1 scale)
4. **Returns hourly forecasts** with cloud coverage

### Input Parameters

```python
hours: int = 24              # Number of hours to forecast
latitude: float = 40.4168    # Location (default: Madrid)
longitude: float = -3.7038   # Location (default: Madrid)
```

### Output

```python
[
    {
        "datetime": datetime(2025, 2, 16, 0, 0),
        "hour": 0,
        "cloud_coverage_pct": 30,          # 30% clouds
        "weather_condition": "Clear",
        "solar_potential": 0.0            # Night = no solar
    },
    {
        "datetime": datetime(2025, 2, 16, 13, 0),
        "hour": 13,
        "cloud_coverage_pct": 20,          # 20% clouds
        "weather_condition": "Clear",
        "solar_potential": 1.0            # Peak solar!
    },
    ...
]
```

### Solar Potential Calculation

```
Solar Potential = Sun Position × Cloud Factor × Weather Factor

Sun Position:
- 06:00-08:00: 0.3 (sunrise)
- 09:00-11:00: 0.7 (morning)
- 12:00-15:00: 1.0 (peak!)
- 16:00-18:00: 0.6 (afternoon)
- 19:00-21:00: 0.2 (sunset)
- 22:00-05:00: 0.0 (night)

Cloud Factor = (100 - cloud_coverage%) / 100

Weather Factor:
- Clear: 1.0
- Clouds: 0.6
- Rain: 0.3
```

### Example Usage

```python
# Agent says: "When should I run the washing machine?"
forecast = fetch_weather_forecast(hours=24)

# Agent finds:
# 13:00 - Solar potential: 1.0 (peak), Clear sky → PERFECT!
# 20:00 - Solar potential: 0.0 (night) → No solar

# Recommendation: "Run washing machine at 13:00-15:00 for maximum self-consumption"
```

### Configuration

Requires optional OpenWeatherMap API key in `.env`:

```bash
OPENWEATHER_API_KEY=your-openweather-key-here
ADVISOR_LATITUDE=40.4168    # Your location
ADVISOR_LONGITUDE=-3.7038   # Your location
```

**Get free key:** https://openweathermap.org/api

### Graceful Degradation

If API unavailable:
- Falls back to **typical weather patterns** for your location
- Uses historical cloud coverage averages
- Solar predictions still reasonably accurate

---

## Tool #3: calculate_savings()

### Purpose
Calculates financial savings from shifting energy usage to cheaper hours.

### What It Does

1. **Analyzes consumption patterns**
2. **Identifies peak usage**
3. **Calculates savings** if shifted to valley hours
4. **Returns ROI in €/year**

### Input Parameters

```python
current_consumption_kwh: float    # Daily consumption (e.g., 15 kWh)
peak_ratio: float                  # Fraction during peak hours (e.g., 0.35)
current_price: float               # Current price (e.g., €0.22/kWh)
valley_price: float = 0.08         # Valley price (default)
```

### Output

```python
{
    "daily_savings_eur": 1.47,           # Save €1.47/day
    "annual_savings_eur": 537.0,         # Save €537/year!
    "peak_consumption_kwh": 5.25,        # Using 5.25 kWh during peak
    "price_diff_eur_kwh": 0.140          # Price difference
}
```

### Calculation Logic

```python
# Example: 15 kWh/day, 35% during peak (€0.22/kWh)
peak_consumption = 15 kWh × 0.35 = 5.25 kWh
price_diff = €0.22 - €0.08 = €0.14/kWh

# Savings if shifted to valley hours (€0.08/kWh)
daily_savings = 5.25 kWh × €0.14 = €0.735
annual_savings = €0.735 × 365 = €268

# But wait! If we shift ALL peak consumption:
# We save €0.14/kWh on 35% of our usage
# That's €268/year just by changing WHEN we use energy!
```

### Example Usage

```python
# Agent analyzes your usage
savings = calculate_savings(
    current_consumption_kwh=15.0,
    peak_ratio=0.35,            # 35% during peak hours
    current_price=0.22          # Paying €0.22/kWh
)

# Agent recommendation:
# "You're using 35% of energy during peak hours (€0.22/kWh).
#  Shifting to valley hours (€0.08/kWh) saves €268/year.
#  Run dishwasher at 22:30 instead of 20:00."
```

### Why This Matters

**Real Impact:**
- Typical household: 15 kWh/day
- Peak usage (35%): 5.25 kWh
- Savings: €268/year just by changing WHEN you use energy
- No investment needed - just behavioral change!

---

## Tool #4: calculate_self_consumption()

### Purpose
Analyzes solar self-consumption and calculates financial value.

### What It Does

1. **Measures solar production**
2. **Tracks self-consumption** (solar you actually use)
3. **Calculates export value** (sold to grid)
4. **Identifies lost value** (opportunity cost)

### Input Parameters

```python
production_kwh: float     # Solar produced (e.g., 20 kWh)
consumption_kwh: float    # Total consumption (e.g., 15 kWh)
export_kwh: float         # Exported to grid (e.g., 5 kWh)
```

### Output

```python
{
    "self_consumed_kwh": 15.0,              # Used 15 kWh of your solar
    "self_consumption_ratio": 1.0,          # 100% self-consumption!
    "export_kwh": 5.0,                      # Exported 5 kWh
    "self_consumed_value_eur": 2.25,        # Worth €2.25
    "export_value_eur": 0.30,               # Worth €0.30 (low!)
    "total_value_eur": 2.55,                # Total value today
    "lost_value_eur": 0.0                   # No lost value (perfect!)
}
```

### Financial Logic

```python
# Self-consumption = production - export
self_consumed = 20 kWh - 5 kWh = 15 kWh

# Financial value
self_consumed_value = 15 kWh × €0.15 = €2.25
export_value = 5 kWh × €0.06 = €0.30

# Why the difference?
# Self-consumed solar saves €0.15/kWh (retail price)
# Exported solar earns €0.06/kWh (feed-in tariff)
# Every kWh self-consumed is worth 2.5× more than exported!

# Lost value calculation
potential_value = 20 kWh × €0.15 = €3.00
actual_value = €2.25 + €0.30 = €2.55
lost_value = €3.00 - €2.55 = €0.45
```

### Example Usage

```python
# Agent analyzes your solar
metrics = calculate_self_consumption(
    production_kwh=20.0,
    consumption_kwh=15.0,
    export_kwh=5.0
)

# Agent sees:
# - Self-consumption ratio: 100% (perfect!)
# - Exported: 5 kWh at €0.06 = €0.30
# - But if you consumed those 5 kWh instead:
#   Value: 5 kWh × €0.15 = €0.75
#   Lost opportunity: €0.75 - €0.30 = €0.45

# Recommendation:
# "Increase self-consumption by shifting usage to solar hours.
#  Run dishwasher at 13:00 instead of 20:00.
#  This could save €0.45/day = €164/year."
```

### Why Self-Consumption Matters

**The Math:**
- Export price: €0.06/kWh (what grid pays you)
- Retail price: €0.15/kWh (what you pay)
- **Self-consumption premium:** 2.5× more valuable!

**Strategy:**
- Use solar when it's produced (12:00-15:00)
- Every kWh self-consumed = €0.09 extra profit
- On 10 kWh/day = €0.90/day = €328/year extra!

---

## How Tools Work Together

### Example: Appliance Scheduling

```
Price Analyst Agent:
  ├─ fetch_pvpc_prices() → Knows prices by hour
  └─ calculate_savings() → Quantifies savings potential

Solar Optimizer Agent:
  ├─ fetch_weather_forecast() → Knows solar production
  └─ calculate_self_consumption() → Optimizes self-consumption

Appliance Scheduler Agent:
  ├─ Uses price data from Price Analyst
  ├─ Uses solar data from Solar Optimizer
  └─ Creates optimal schedule

Coordinator Agent:
  └─ Synthesizes all recommendations
```

### Real-World Example

```python
# Scenario: User wants to run dishwasher

# 1. Price Analyst checks prices
prices = fetch_pvpc_prices()
# 20:00 = €0.22/kWh (peak) → Expensive!
# 13:00 = €0.15/kWh (flat) → Cheaper

# 2. Solar Optimizer checks weather
forecast = fetch_weather_forecast()
# 13:00 = Solar potential 1.0 (peak production)
# 20:00 = Solar potential 0.0 (no solar)

# 3. Appliance Scheduler calculates
savings = calculate_savings(
    current_consumption_kwh=1.5,    # Dishwasher uses 1.5 kWh
    peak_ratio=1.0,                 # Currently at peak hour
    current_price=0.22
)
# Running at 20:00 costs €0.33
# Running at 13:00 costs €0.23
# Savings: €0.10 per load = €36/year

# 4. Solar Optimizer calculates
solar_metrics = calculate_self_consumption(
    production_kwh=3.0,             # Solar producing 3 kW at 13:00
    consumption_kwh=4.5,            # Using 4.5 kW total
    export_kwh=0.0                  # No export (perfect!)
)
# Self-consumption at 13:00 = 100%!

# 5. Final recommendation
# "Run dishwasher at 13:00-15:30 instead of 20:00-22:30.
#  You'll use free solar power (€0.23) instead of grid power (€0.33).
#  Savings: €0.10/load = €36/year"
```

---

## Tool Configuration

### Environment Variables

```bash
# Required for real-time prices (optional - has fallback)
ESIOS_TOKEN=your-esios-token-here

# Required for weather forecasts (optional - has fallback)
OPENWEATHER_API_KEY=your-openweather-key-here

# Location for weather forecasts
ADVISOR_LATITUDE=40.4168    # Your latitude
ADVISOR_LONGITUDE=-3.7038   # Your longitude
```

### Graceful Degradation

All tools have fallbacks:

| Tool | With API | Without API |
|------|----------|-------------|
| fetch_pvpc_prices | Real-time prices | Estimated prices |
| fetch_weather_forecast | Actual forecast | Typical patterns |
| calculate_savings | Always works | Always works |
| calculate_self_consumption | Always works | Always works |

**Result:** System works with or without API keys!

---

## Tool Registry

Tools are registered in `external_apis.py`:

```python
JAATO_TOOLS = {
    "fetch_pvpc_prices": fetch_pvpc_prices,
    "fetch_weather_forecast": fetch_weather_forecast,
    "calculate_savings": calculate_savings,
    "calculate_self_consumption": calculate_self_consumption,
}
```

Agents can call tools by name:

```python
# Agent code
tool = get_tool("fetch_pvpc_prices")
prices = tool(date=datetime.now())
```

---

## Testing Tools

Test all tools:

```bash
cd /home/apanoia/Sources/enphase_monitoring
python3 -c "
import sys
sys.path.insert(0, 'src')
from external_apis import *

# Test price fetching
prices = fetch_pvpc_prices()
print(f'Prices: {len(prices)} hours')

# Test weather
forecast = fetch_weather_forecast(hours=12)
print(f'Forecast: {len(forecast)} hours')

# Test savings
savings = calculate_savings(15.0, 0.35, 0.22)
print(f'Savings: €{savings[\"annual_savings_eur\"]}/year')

# Test self-consumption
metrics = calculate_self_consumption(20.0, 15.0, 5.0)
print(f'Self-consumption: {metrics[\"self_consumption_ratio\"]:.1%}')
"
```

---

## Summary

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| **fetch_pvpc_prices** | Get electricity prices | Date | 24 hourly prices |
| **fetch_weather_forecast** | Get solar production forecast | Hours, location | Hourly forecasts |
| **calculate_savings** | Calculate ROI from load shifting | Consumption, peak ratio | €/year savings |
| **calculate_self_consumption** | Analyze solar usage | Production, consumption, export | Metrics + value |

**Key Benefits:**
- ✅ Real-world data integration
- ✅ Quantified recommendations (€/year)
- ✅ Graceful degradation (works without APIs)
- ✅ Easy to extend with new tools
- ✅ Agents can make data-driven decisions

These tools transform the Jaato advisor from a simple chatbot into a sophisticated energy optimization system! 🚀
