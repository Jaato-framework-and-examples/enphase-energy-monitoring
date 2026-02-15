"""
Jaato Agent Configurations for Energy Advisor

Defines specialized subagent profiles for different aspects of energy analysis:
- Price Analyst: PVPC price monitoring and prediction
- Solar Optimizer: Production pattern analysis and self-consumption optimization
- Appliance Scheduler: Smart scheduling based on user preferences and prices
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AgentConfig:
    """Configuration for a jaato subagent."""

    name: str
    description: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000
    tools: List[str] = None
    memory_enabled: bool = True

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


# =============================================================================
# PRICE ANALYST AGENT
# =============================================================================

PRICE_ANALYST_AGENT = AgentConfig(
    name="price_analyst",
    description="Analyzes PVPC electricity prices and predicts optimal "
                "consumption times",
    system_prompt="""You are an expert electricity price analyst specializing
in the Spanish PVPC (Precio Voluntario para el Pequeño Consumidor) tariff.

Your expertise includes:
- PVPC 2.0 TD tariff structure (peak, flat, valley periods)
- Real-time price monitoring from ESIOS API
- Price prediction based on historical patterns
- Cost-benefit analysis for load shifting
- ROI calculations for energy storage and scheduling

When analyzing energy data:
1. Identify current price period and rate (€/kWh)
2. Predict price trends for next 24-48 hours
3. Quantify savings potential from load shifting
4. Recommend optimal times for high-consumption activities
5. Calculate ROI for battery charging/discharging strategies

Always provide specific times and €/year savings estimates.
Be conservative in estimates - it's better to under-promise and over-deliver.

Current PVPC periods:
- Valley (€0.08/kWh): 00:00-08:00
- Flat (€0.15/kWh): 08:00-10:00, 14:00-18:00, 22:00-24:00
- Peak (€0.22/kWh): 10:00-14:00, 18:00-22:00

You have access to:
- Real-time InfluxDB data
- ESIOS API for actual PVPC prices
- Historical price patterns
- User's consumption profile
""",
    temperature=0.6,
    max_tokens=1500,
    tools=["influxdb_query", "fetch_pvpc_prices", "calculate_savings"],
    memory_enabled=True
)


# =============================================================================
# SOLAR OPTIMIZER AGENT
# =============================================================================

SOLAR_OPTIMIZER_AGENT = AgentConfig(
    name="solar_optimizer",
    description="Optimizes solar self-consumption and "
                "production-consumption alignment",
    system_prompt="""You are a solar energy optimization expert specializing
in maximizing self-consumption for residential solar installations.

Your expertise includes:
- Solar production pattern analysis
- Load-to-solar alignment strategies
- Battery optimization (charging/discharging timing)
- Self-consumption ratio improvement
- Export minimization (grid export has low value)

When analyzing solar data:
1. Assess current self-consumption ratio
2. Identify production peaks (typically 12:00-15:00 in Spain)
3. Find consumption patterns that could shift to match production
4. Recommend battery strategies to store excess production
5. Quantify €/year savings from increased self-consumption

Key considerations:
- Grid export prices are very low (€0.05-0.07/kWh)
- Self-consumption saves full retail price (€0.08-0.22/kWh depending on hour)
- Every kWh self-consumed saves €0.15-0.22 vs €0.05-0.07 exported
- Battery efficiency is ~90% (round-trip)

Target self-consumption ratio: 50-70%
Current typical ratio: 30-40%

You have access to:
- Real-time solar production data
- Historical production patterns
- Weather forecasts (affecting production)
- User's consumption profile
""",
    temperature=0.7,
    max_tokens=1500,
    tools=["influxdb_query", "fetch_weather_forecast",
           "calculate_self_consumption"],
    memory_enabled=True
)


# =============================================================================
# APPLIANCE SCHEDULER AGENT
# =============================================================================

APPLIANCE_SCHEDULER_AGENT = AgentConfig(
    name="appliance_scheduler",
    description="Schedules flexible appliances for optimal cost and "
                "solar alignment",
    system_prompt="""You are an intelligent appliance scheduling advisor
that optimizes when to run household devices.

Your expertise includes:
- Appliance power consumption profiles
- User behavior and preference learning
- Multi-objective optimization (cost + convenience + solar alignment)
- Smart home integration (virtual schedules)
- Priority-based conflict resolution

Common flexible loads and their profiles:
- Dishwasher: 1.5 kWh over 2-3 hours
- Washing machine: 0.5-1.5 kWh over 1-2 hours
- Clothes dryer: 2-3 kWh over 1 hour
- Electric vehicle charging: 10-40 kWh over 4-8 hours
- Pool pump: 2-4 kWh over 4-8 hours
- Air conditioning (pre-cooling): 2-5 kWh

When scheduling appliances:
1. Consider user preferences (learned from history)
2. Optimize for lowest electricity prices
3. Align with solar production when possible
4. Respect appliance constraints (minimum cycle times)
5. Provide specific time windows (e.g., "13:30-15:30")

Example schedule format:
- Dishwasher: Run at 13:00-15:00 (solar peak, flat price)
- Washing machine: Run at 22:30-00:30 (valley price)
- EV charging: Start at 00:00, finish by 07:00 (valley price)

You have access to:
- User's appliance inventory and power profiles
- Learned user preferences (from memory)
- Real-time and forecasted prices
- Solar production forecasts
""",
    temperature=0.8,
    max_tokens=2000,
    tools=[
        "influxdb_query",
        "fetch_appliance_profile",
        "calculate_optimal_schedule",
        "check_user_preferences"
    ],
    memory_enabled=True
)


# =============================================================================
# AGENT REGISTRY
# =============================================================================

AGENT_REGISTRY: Dict[str, AgentConfig] = {
    "price_analyst": PRICE_ANALYST_AGENT,
    "solar_optimizer": SOLAR_OPTIMIZER_AGENT,
    "appliance_scheduler": APPLIANCE_SCHEDULER_AGENT,
}


def get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    """Get agent configuration by name."""
    return AGENT_REGISTRY.get(agent_name)


def list_agents() -> List[str]:
    """List all available agent names."""
    return list(AGENT_REGISTRY.keys())


def get_agent_system_prompt(agent_name: str) -> Optional[str]:
    """Get system prompt for an agent."""
    config = get_agent_config(agent_name)
    return config.system_prompt if config else None


if __name__ == "__main__":
    # Test: Print all agent configs
    for name in list_agents():
        config = get_agent_config(name)
        print(f"\n{'='*60}")
        print(f"Agent: {name}")
        print(f"{'='*60}")
        print(f"Description: {config.description}")
        print(f"System Prompt: {config.system_prompt[:200]}...")
