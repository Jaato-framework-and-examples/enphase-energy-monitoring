#!/usr/bin/env python3
"""
Jaato-Powered Smart Energy Advisor

Drives three specialist jaato agents (price_analyst, solar_optimizer,
appliance_scheduler) over the current jaato SDK to produce home-energy
recommendations.

Architecture:
- Energy context (live readings + 24h patterns) is fetched from InfluxDB in
  Python and embedded into each agent's prompt — the agents have no tools.
- Each specialist runs in its own jaato session, selected from the
  `.jaato/profiles/` profile-set via JAATO_PROFILE_SET + the agent persona in
  `.jaato/agents/<name>.md`. Sessions run sequentially on one API client.
- Each specialist turn runs through the jaato-sdk convenience facade
  (`IPCClient.session` + `s.ask`), which owns the send-and-wait recipe.

Preflight: python -m jaato_sdk.doctor --workspace . --env-file .env
"""

import argparse
import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from jaato_sdk import IPCClient, ClientType, AgentError

from influxdb_client import InfluxDBClient

# Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "energy_monitoring")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "home_energy")

JAATO_SOCKET = os.getenv("JAATO_SOCKET", "/tmp/jaato.sock")
ENV_FILE = os.getenv("JAATO_ENV_FILE", ".env")
WORKSPACE = os.getenv("JAATO_WORKSPACE", str(Path(__file__).resolve().parent.parent))

# The specialists run in this order; each name is both the profile name (within
# the active JAATO_PROFILE_SET) and the agent persona under .jaato/agents/.
SPECIALISTS: List[str] = ["price_analyst", "solar_optimizer", "appliance_scheduler"]

SPECIALIST_TASKS: Dict[str, str] = {
    "price_analyst":
        "Analyze the price exposure in the data above and recommend specific "
        "load-shifting actions with €/year savings estimates.",
    "solar_optimizer":
        "Analyze the solar self-consumption in the data above and recommend "
        "alignment/battery strategies with €/year savings estimates.",
    "appliance_scheduler":
        "Produce a concrete appliance schedule (specific time windows) based on "
        "the prices and solar production in the data above, with €/year savings.",
}

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


class InfluxDBFetcher:
    """Fetches energy data from InfluxDB."""

    def __init__(self, url: str, token: str = ""):
        self.client = InfluxDBClient(
            url=url,
            token=token if token else None,
            org=INFLUXDB_ORG
        )
        self.bucket = INFLUXDB_BUCKET

    async def get_current_readings(self) -> Dict[str, float]:
        """Get current energy readings using Flux query.

        The collector writes measurement ``energy_readings`` with fields
        ``home_consumption_w`` and ``solar_production_w``. Grid import/export
        are not metered, so they are derived from the consumption/production
        balance: import = max(0, cons - prod), export = max(0, prod - cons).
        """
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -10m)
          |> filter(fn: (r) => r["_measurement"] == "energy_readings")
          |> last(column: "_time")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["home_consumption_w", "solar_production_w"])
        '''

        try:
            result = self.client.query_api().query(query=query)

            consumption = production = 0.0
            for table in result:
                for record in table.records:
                    c = record.values.get("home_consumption_w")
                    p = record.values.get("solar_production_w")
                    if c is not None:
                        consumption = float(c)
                    if p is not None:
                        production = float(p)

            return {
                "consumption": consumption,
                "production": production,
                "import": max(0.0, consumption - production),
                "export": max(0.0, production - consumption),
            }

        except Exception as e:
            logger.error(f"Failed to fetch current readings: {e}")
            return {"consumption": 0.0, "production": 0.0, "import": 0.0, "export": 0.0}

    async def get_hourly_patterns(self, hours: int = 24) -> Dict[str, Dict[int, float]]:
        """Get hourly consumption and production patterns using Flux query."""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "energy_readings")
          |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["_time", "home_consumption_w", "solar_production_w"])
        '''

        try:
            result = self.client.query_api().query(query=query)

            hourly_consumption = {i: 0.0 for i in range(24)}
            hourly_production = {i: 0.0 for i in range(24)}

            for table in result:
                for record in table.records:
                    time_val = record.values.get("_time")
                    if time_val:
                        hour = time_val.hour
                        consumption = record.values.get("home_consumption_w")
                        production = record.values.get("solar_production_w")

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


def build_context_block(context: EnergyContext, prices: PriceEstimator) -> str:
    """Render the shared energy-data block sent to every specialist agent."""
    total_consumption = sum(context.hourly_consumption.values()) / 1000  # kWh
    peak_hours = [h for h in range(24) if prices.get_period(h) == "peak"]
    peak_consumption = sum(
        context.hourly_consumption.get(h, 0) for h in peak_hours
    ) / 1000
    peak_ratio = peak_consumption / total_consumption if total_consumption > 0 else 0

    block = f"""## Current Energy Situation (as of {datetime.now().strftime('%Y-%m-%d %H:%M')})

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
    for hour in sorted(context.hourly_consumption.keys()):
        period = prices.get_period(hour)
        price = prices.get_price(hour)
        consumption = context.hourly_consumption.get(hour, 0)
        block += f"  {hour:02d}:00 [{period:5s} €{price:.2f}] {consumption:6.0f} W\n"

    return block


class JaatoEnergyAdvisor:
    """Orchestrates the three specialist jaato agents."""

    def __init__(
        self,
        jaato_socket: str = JAATO_SOCKET,
        env_file: str = ENV_FILE,
        workspace: str = WORKSPACE,
        influxdb_url: str = INFLUXDB_URL,
        influxdb_token: str = INFLUXDB_TOKEN,
    ):
        # Connection knobs reused by run_specialist's per-session facade calls.
        self.jaato_socket = jaato_socket
        self.env_file = env_file          # never None (handshake crashes on None)
        self.workspace = workspace
        self.client = IPCClient(
            jaato_socket,
            client_type=ClientType.API,   # load-bearing: keeps signal_completion
            auto_start=True,
            env_file=env_file,
            workspace_path=workspace,
        )
        self.influxdb = InfluxDBFetcher(url=influxdb_url, token=influxdb_token)
        self.prices = PriceEstimator()
        self._running = False

    async def initialize(self) -> bool:
        """Wait for InfluxDB, then connect (and cold-autostart) the daemon."""
        logger.info("Initializing Jaato Energy Advisor...")

        parsed = urlparse(INFLUXDB_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8086
        logger.info(f"Waiting for InfluxDB at {host}:{port} ...")
        for _ in range(10):
            sock = socket.socket()
            sock.settimeout(1)
            ready = sock.connect_ex((host, port)) == 0
            sock.close()
            if ready:
                logger.info("✓ InfluxDB is ready")
                break
            await asyncio.sleep(1)

        logger.info("Connecting to jaato daemon (cold autostart ~30-60s) ...")
        if not await self.client.connect(timeout=120.0):
            logger.error("Failed to connect/autostart jaato daemon — run the doctor")
            return False
        logger.info("✓ Connected to jaato daemon")
        return True

    async def build_context(self) -> EnergyContext:
        """Build current energy context from InfluxDB."""
        logger.info("Building energy context...")
        now = datetime.now()

        readings = await self.influxdb.get_current_readings()
        patterns = await self.influxdb.get_hourly_patterns(hours=24)

        current_hour = now.hour
        return EnergyContext(
            current_consumption_w=readings["consumption"],
            current_production_w=readings["production"],
            grid_import_w=readings["import"],
            grid_export_w=readings["export"],
            current_hour=current_hour,
            current_day_of_week=now.weekday(),
            current_price_eur_kwh=self.prices.get_price(current_hour),
            price_period=self.prices.get_period(current_hour),
            hourly_consumption=patterns["consumption"],
            hourly_production=patterns["production"],
        )

    async def run_specialist(
        self, agent_name: str, prompt: str, timeout: float = 180.0
    ) -> Dict[str, Any]:
        """Run one specialist in its own session and collect its text output."""
        logger.info(f"Running specialist: {agent_name}")
        try:
            # profile + agent both name the stage; JAATO_PROFILE_SET (from .env)
            # selects the provider/model tier. The facade owns connect →
            # create_session → send-and-wait → disconnect; sources=None
            # collects every output chunk, matching the old on_output (which
            # appended all output, not just the model source).
            async with IPCClient.session(
                profile=agent_name,
                agent=agent_name,
                client_type=ClientType.API,
                env_file=self.env_file,
                workspace_path=self.workspace,
                socket_path=self.jaato_socket,
            ) as s:
                text = await asyncio.wait_for(
                    s.ask(prompt, sources=None), timeout=timeout
                )
            return {"agent": agent_name, "text": text, "error": None}
        except AgentError as e:
            # Per-specialist fault isolation: an error terminal now raises, so
            # one failing specialist must not abort the whole analysis.
            return {"agent": agent_name, "text": "", "error": str(e)}
        except asyncio.TimeoutError:
            return {"agent": agent_name, "text": "",
                    "error": f"timeout after {timeout}s waiting for turn completion"}

    async def analyze_once(self) -> Dict[str, Any]:
        """Build context once, then run every specialist over it."""
        logger.info("Starting one-shot analysis...")
        context = await self.build_context()
        context_block = build_context_block(context, self.prices)

        analysis_start = datetime.now()
        specialists: List[Dict[str, Any]] = []
        for agent_name in SPECIALISTS:
            prompt = (
                f"{context_block}\n\n## Your Task\n\n{SPECIALIST_TASKS[agent_name]}\n"
            )
            result = await self.run_specialist(agent_name, prompt)
            specialists.append(result)
            if result["error"]:
                logger.warning(f"[{agent_name}] {result['error']}")
            else:
                logger.info(f"[{agent_name}] {len(result['text'])} chars")

        duration = (datetime.now() - analysis_start).total_seconds()
        result = {
            "timestamp": datetime.now().isoformat(),
            "context": {
                "consumption_w": context.current_consumption_w,
                "production_w": context.current_production_w,
                "price_eur_kwh": context.current_price_eur_kwh,
                "price_period": context.price_period,
            },
            "specialists": specialists,
            "duration_seconds": duration,
        }
        logger.info(f"Analysis completed in {duration:.1f}s")
        return result

    async def start_streaming(self, interval_seconds: int = 300):
        """Run analysis on a fixed interval until stopped."""
        logger.info(f"Starting continuous analysis (interval: {interval_seconds}s)")
        self._running = True
        while self._running:
            try:
                result = await self.analyze_once()
                logger.info("=" * 60)
                logger.info("ANALYSIS RESULT:")
                logger.info(json.dumps(result, indent=2, default=str))
                logger.info("=" * 60)
                logger.info(f"Waiting {interval_seconds}s until next analysis...")
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error during analysis: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def stop(self):
        """Stop the advisor and disconnect."""
        logger.info("Stopping Jaato Energy Advisor...")
        self._running = False
        await self.client.disconnect()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Jaato-Powered Smart Energy Advisor")
    parser.add_argument('--jaato-socket', default=JAATO_SOCKET, help='jaato server socket')
    parser.add_argument('--influxdb-url', default=INFLUXDB_URL, help='InfluxDB URL')
    parser.add_argument('--analyze-once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=300,
                        help='Analysis interval in seconds (default: 300)')
    args = parser.parse_args()

    advisor = JaatoEnergyAdvisor(
        jaato_socket=args.jaato_socket,
        influxdb_url=args.influxdb_url,
    )

    if not await advisor.initialize():
        logger.error("Failed to initialize advisor")
        return 1

    try:
        if args.analyze_once:
            result = await advisor.analyze_once()
            print("\n" + "=" * 60)
            print("ANALYSIS RESULT:")
            print("=" * 60)
            print(json.dumps(result, indent=2, default=str))
        else:
            await advisor.start_streaming(interval_seconds=args.interval)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await advisor.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
