#!/usr/bin/env python3
"""
Jaato-Powered Smart Energy Advisor

Replaces Ollama with jaato agents for intelligent energy recommendations.
Features:
- Real-time streaming insights via jaato event system
- Specialized subagents for price analysis, solar optimization, appliance scheduling
- Memory system for learning user preferences
- Tool use for external APIs (PVPC prices, weather forecasts)
- Multi-agent reasoning with coordinated planning
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncIterator

import sys

sys.path.insert(
    0,
    str(Path(__file__).parent.parent / ".venv/lib/python3.12/site-packages")
)

try:
    from jaato_sdk.client import IPCRecoveryClient, ConnectionState
    from jaato_sdk.events import Event, EventType
    JAATO_SDK_AVAILABLE = True
except ImportError:
    JAATO_SDK_AVAILABLE = False

try:
    from influxdb_client import InfluxDBClient
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = ""
INFLUXDB_ORG = "energy_monitoring"
INFLUXDB_BUCKET = "home_energy"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EnergyContext:
    """Context data for energy analysis."""
    current_consumption_w: float = 0.0
    current_production_w: float = 0.0
    grid_import_w: float = 0.0
    grid_export_w: float = 0.0
    battery_level_pct: Optional[float] = None
    current_hour: int = 0
    current_day_of_week: int = 0
    
    # Price information
    current_price_eur_kwh: float = 0.15
    price_period: str = "flat"  # peak, flat, valley
    
    # Historical patterns (last 24h)
    hourly_consumption: Dict[int, float] = field(default_factory=dict)
    hourly_production: Dict[int, float] = field(default_factory=dict)
    
    # User preferences (from memory)
    appliance_schedules: Dict[str, str] = field(default_factory=dict)
    flexible_loads: List[str] = field(default_factory=list)
    preferred_analysis_times: List[int] = field(default_factory=list)


class JaatoClientWrapper:
    """Wrapper for jaato SDK client with automatic reconnection."""
    
    def __init__(
        self,
        socket_path: str = "/tmp/jaato.sock",
        auto_start: bool = True,
        env_file: str = ".env"
    ):
        if not JAATO_SDK_AVAILABLE:
            raise RuntimeError("jaato-sdk not available. Install with: pip install jaato-sdk")
        
        self.socket_path = socket_path
        self.client = IPCRecoveryClient(
            socket_path=socket_path,
            auto_start=auto_start,
            env_file=env_file
        )
        self._connected = False
        
    async def connect(self) -> bool:
        """Connect to jaato server."""
        try:
            await self.client.connect()
            self._connected = True
            logger.info(f"Connected to jaato server at {self.socket_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to jaato server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from jaato server."""
        if self._connected:
            await self.client.disconnect()
            self._connected = False
            logger.info("Disconnected from jaato server")
    
    async def send_message(self, message: str) -> AsyncIterator[Event]:
        """Send message and stream response events."""
        if not self._connected:
            raise RuntimeError("Not connected to jaato server")
        
        async for event in self.client.send_message_and_stream(message):
            yield event
    
    async def get_events(self) -> AsyncIterator[Event]:
        """Get all events from server."""
        if not self._connected:
            raise RuntimeError("Not connected to jaato server")
        
        async for event in self.client.events():
            yield event
    
    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self.client.state if self._connected else ConnectionState.DISCONNECTED


class InfluxDBFetcher:
    """Fetches energy data from InfluxDB."""
    
    def __init__(self, url: str, token: str = ""):
        if not INFLUXDB_AVAILABLE:
            raise RuntimeError("InfluxDB client not available")
        
        self.client = InfluxDBClient(
            url=url,
            token=token if token else None,
            org=INFLUXDB_ORG
        )
        self.bucket = INFLUXDB_BUCKET
    
    async def get_current_readings(self) -> Dict[str, float]:
        """Get current energy readings."""
        query = f'''
        SELECT last("grid_consumption_w") as consumption,
               last("solar_production_w") as production,
               last("grid_import_w") as import_w,
               last("grid_export_w") as export_w
        FROM "{self.bucket}"
        WHERE time > now() - 5m
        '''
        
        try:
            result = self.client.query_api().query(query=query)
            
            readings = {
                "consumption": 0.0,
                "production": 0.0,
                "import": 0.0,
                "export": 0.0
            }
            
            for table in result:
                for record in table.records:
                    for key in readings.keys():
                        value = record.get_value()
                        if value is not None:
                            readings[key] = float(value)
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to fetch current readings: {e}")
            return {"consumption": 0.0, "production": 0.0, "import": 0.0, "export": 0.0}
    
    async def get_hourly_patterns(self, hours: int = 24) -> Dict[str, Dict[int, float]]:
        """Get hourly consumption and production patterns."""
        query = f'''
        SELECT MEAN("grid_consumption_w") as consumption,
               MEAN("solar_production_w") as production
        FROM "{self.bucket}"
        WHERE time > now() - {hours}h
        GROUP BY time(1h)
        '''
        
        try:
            result = self.client.query_api().query(query=query)
            
            hourly_consumption = {i: 0.0 for i in range(24)}
            hourly_production = {i: 0.0 for i in range(24)}
            
            for table in result:
                for record in table.records:
                    hour = record.get_time().hour
                    consumption = record.values.get("consumption")
                    production = record.values.get("production")
                    
                    if consumption is not None:
                        hourly_consumption[hour] = float(consumption)
                    if production is not None:
                        hourly_production[hour] = float(production)
            
            return {
                "consumption": hourly_consumption,
                "production": hourly_production
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch hourly patterns: {e}")
            return {"consumption": {}, "production": {}}


class PriceEstimator:
    """Estimates electricity prices using PVPC data."""
    
    PVPC_PRICES = {
        "peak": 0.22,      # 10:00-14:00, 18:00-22:00
        "flat": 0.15,      # 08:00-10:00, 14:00-18:00, 22:00-24:00
        "valley": 0.08     # 00:00-08:00
    }
    
    @staticmethod
    def get_period(hour: int) -> str:
        """Determine price period for hour."""
        if 0 <= hour < 8:
            return "valley"
        elif 8 <= hour < 10:
            return "flat"
        elif 10 <= hour < 14:
            return "peak"
        elif 14 <= hour < 18:
            return "flat"
        elif 18 <= hour < 22:
            return "peak"
        else:
            return "flat"
    
    @staticmethod
    def get_price(hour: int) -> float:
        """Get price for hour."""
        period = PriceEstimator.get_period(hour)
        return PriceEstimator.PVPC_PRICES[period]


class JaatoEnergyAdvisor:
    """Main advisor using jaato agents for intelligent recommendations."""
    
    def __init__(
        self,
        jaato_socket: str = "/tmp/jaato.sock",
        influxdb_url: str = INFLUXDB_URL,
        influxdb_token: str = ""
    ):
        self.jaato = JaatoClientWrapper(socket_path=jaato_socket)
        self.influxdb = InfluxDBFetcher(url=influxdb_url, token=influxdb_token)
        self.price_estimator = PriceEstimator()
        
        self._running = False
        self._context_cache: Optional[EnergyContext] = None
    
    async def initialize(self) -> bool:
        """Initialize connections."""
        logger.info("Initializing Jaato Energy Advisor...")
        
        # Connect to jaato server
        if not await self.jaato.connect():
            logger.error("Failed to connect to jaato server")
            return False
        
        logger.info("✓ Connected to jaato server")
        return True
    
    async def build_context(self) -> EnergyContext:
        """Build current energy context from InfluxDB."""
        logger.info("Building energy context...")
        
        now = datetime.now()
        
        # Get current readings
        readings = await self.influxdb.get_current_readings()
        
        # Get hourly patterns
        patterns = await self.influxdb.get_hourly_patterns(hours=24)
        
        # Get price info
        current_hour = now.hour
        current_price = self.price_estimator.get_price(current_hour)
        current_period = self.price_estimator.get_period(current_hour)
        
        context = EnergyContext(
            current_consumption_w=readings["consumption"],
            current_production_w=readings["production"],
            grid_import_w=readings["import"],
            grid_export_w=readings["export"],
            current_hour=current_hour,
            current_day_of_week=now.weekday(),
            current_price_eur_kwh=current_price,
            price_period=current_period,
            hourly_consumption=patterns["consumption"],
            hourly_production=patterns["production"]
        )
        
        self._context_cache = context
        return context
    
    def create_analysis_prompt(self, context: EnergyContext) -> str:
        """Create detailed prompt for jaato agents."""
        
        # Calculate some metrics
        total_consumption = sum(context.hourly_consumption.values()) / 1000  # kW
        peak_hours = [h for h in range(24) if self.price_estimator.get_period(h) == "peak"]
        peak_consumption = sum(
            context.hourly_consumption.get(h, 0) 
            for h in peak_hours
        ) / 1000
        peak_ratio = peak_consumption / total_consumption if total_consumption > 0 else 0
        
        prompt = f"""You are an expert home energy advisor with access to real-time data and predictive analytics.

## Current Energy Situation (as of {datetime.now().strftime('%Y-%m-%d %H:%M')})

### Live Readings:
- Current consumption: {context.current_consumption_w:.0f} W
- Solar production: {context.current_production_w:.0f} W
- Grid import: {context.grid_import_w:.0f} W
- Grid export: {context.grid_export_w:.0f} W

### Price Context:
- Current hour: {context.current_hour}:00
- Price period: {context.price_period.upper()}
- Current electricity price: €{context.current_price_eur_kwh:.3f}/kWh

### 24-Hour Patterns:
- Total daily consumption: {total_consumption:.1f} kWh
- Peak hours consumption (10-14, 18-22): {peak_consumption:.1f} kWh
- Peak consumption ratio: {peak_ratio:.1%}

### Hourly Consumption (last 24h):
"""
        # Add hourly breakdown
        for hour in sorted(context.hourly_consumption.keys()):
            period = self.price_estimator.get_period(hour)
            price = self.price_estimator.get_price(hour)
            consumption = context.hourly_consumption.get(hour, 0)
            prompt += f"  {hour:02d}:00 [{period:5s} €{price:.2f}] {consumption:6.0f} W\n"
        
        prompt += """
## Your Task

Provide 3-5 specific, actionable recommendations focusing on:

1. **Immediate Actions** (next 24 hours)
   - What should the user do RIGHT NOW or schedule for today/tomorrow?
   - Consider current price period and production levels

2. **Appliance Scheduling**
   - When to run dishwasher, washing machine, etc. for maximum savings?
   - Be specific with times (e.g., "Run dishwasher at 13:30-15:30")

3. **Solar Self-Consumption**
   - How to align consumption with solar production?
   - Which hours offer best solar-to-consumption ratio?

4. **Cost Optimization**
   - Quantify potential savings in €/year for each recommendation
   - Consider shifting peak consumption to valley hours

5. **Pattern Insights**
   - Any unusual patterns you notice?
   - Long-term optimization opportunities?

For each recommendation, provide:
- **Title**: Brief, actionable description
- **Why**: Rationale based on the data
- **When**: Specific time window
- **Savings**: Estimated €/year
- **Confidence**: High/Medium/Low

Be specific, data-driven, and actionable. The user is in Spain with PVPC tariff.
"""
        return prompt
    
    async def analyze_once(self) -> Dict[str, Any]:
        """Perform one-shot analysis and return results."""
        logger.info("Starting one-shot analysis...")
        
        # Build context
        context = await self.build_context()
        
        # Create prompt
        prompt = self.create_analysis_prompt(context)
        
        # Send to jaato and collect response
        logger.info("Sending analysis request to jaato agents...")
        
        full_response = []
        analysis_start = datetime.now()
        
        async for event in self.jaato.send_message(prompt):
            full_response.append(str(event))
            
            # Stream output in real-time
            if event.type == EventType.AGENT_OUTPUT:
                logger.info(f"[JAATO] {event.content}")
        
        analysis_duration = (datetime.now() - analysis_start).total_seconds()
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "context": {
                "consumption_w": context.current_consumption_w,
                "production_w": context.current_production_w,
                "price_eur_kwh": context.current_price_eur_kwh,
                "price_period": context.price_period
            },
            "analysis": "".join(full_response),
            "duration_seconds": analysis_duration
        }
        
        logger.info(f"Analysis completed in {analysis_duration:.1f}s")
        return result
    
    async def start_streaming(self, interval_seconds: int = 300):
        """Start continuous streaming analysis."""
        logger.info(f"Starting continuous analysis (interval: {interval_seconds}s)")
        self._running = True
        
        while self._running:
            try:
                # Perform analysis
                result = await self.analyze_once()
                
                # Emit result as event (could be sent to external system)
                logger.info("=" * 60)
                logger.info("ANALYSIS RESULT:")
                logger.info(json.dumps(result, indent=2, default=str))
                logger.info("=" * 60)
                
                # Wait for next interval
                logger.info(f"Waiting {interval_seconds}s until next analysis...")
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error during analysis: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
    
    async def stop(self):
        """Stop the advisor."""
        logger.info("Stopping Jaato Energy Advisor...")
        self._running = False
        await self.jaato.disconnect()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Jaato-Powered Smart Energy Advisor"
    )
    parser.add_argument(
        '--jaato-socket',
        default='/tmp/jaato.sock',
        help='Path to jaato server socket'
    )
    parser.add_argument(
        '--influxdb-url',
        default=INFLUXDB_URL,
        help='InfluxDB URL'
    )
    parser.add_argument(
        '--analyze-once',
        action='store_true',
        help='Run analysis once and exit'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Analysis interval in seconds (default: 300 = 5 min)'
    )
    
    args = parser.parse_args()
    
    # Create advisor
    advisor = JaatoEnergyAdvisor(
        jaato_socket=args.jaato_socket,
        influxdb_url=args.influxdb_url
    )
    
    # Initialize
    if not await advisor.initialize():
        logger.error("Failed to initialize advisor")
        return 1
    
    try:
        if args.analyze_once:
            # Single analysis
            result = await advisor.analyze_once()
            print("\n" + "=" * 60)
            print("ANALYSIS RESULT:")
            print("=" * 60)
            print(json.dumps(result, indent=2, default=str))
        else:
            # Continuous streaming
            await advisor.start_streaming(interval_seconds=args.interval)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    
    finally:
        await advisor.stop()
    
    return 0


if __name__ == "__main__":
    if not JAATO_SDK_AVAILABLE:
        logger.error("jaato-sdk is not installed. Install with:")
        logger.error("  pip install jaato-sdk")
        sys.exit(1)
    
    exit(asyncio.run(main()))
