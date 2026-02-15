#!/usr/bin/env python3
"""
Enphase Gateway Data Collector Daemon

Polls Enphase gateway for solar production, grid consumption, and export data.
Stores measurements in InfluxDB time-series database.

Author: Energy Monitoring System
Version: 1.0.0
"""

import requests
import urllib3
import time
import logging

# Suppress InsecureRequestWarning for self-signed gateway certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime
from typing import Optional, Dict, Any
import argparse
import sys
import signal
import json

# InfluxDB client library
try:
    from influxdb_client import InfluxDBClient, Point
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    print("WARNING: influxdb-client not installed. Install with: pip install influxdb-client", file=sys.stderr)

try:
    from enphase_token import EnphaseTokenManager
    ENPHASE_TOKEN_AVAILABLE = True
except ImportError:
    ENPHASE_TOKEN_AVAILABLE = False
    print("WARNING: enphase_token module not available. Install: pip install -e .", file=sys.stderr)

# Configuration
# Load from environment variables set in .env file
# This allows single source of truth for configuration

import os

ENPHASE_TOKEN_CACHE_DIR = os.getenv("ENPHASE_TOKEN_CACHE", "/tmp/.enphase_tokens")
ENLIGHTEN_EMAIL = os.getenv("ENLIGHTEN_EMAIL", "")
ENLIGHTEN_PASSWORD = os.getenv("ENLIGHTEN_PASSWORD", "")
POLL_INTERVAL_SECONDS = int(os.getenv("ENPHASE_POLL_INTERVAL_SECONDS", "300"))  # Default: 5 minutes
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = "energy_monitoring"
INFLUXDB_BUCKET = "home_energy"
INFLUXDB_RETENTION_DAYS = 30

# Gateway configuration from environment (optional)
# If set, discovery is skipped and these values are used directly
ENPHASE_GATEWAY_IP = os.getenv("ENPHASE_GATEWAY_IP", "")
ENPHASE_GATEWAY_SERIAL = os.getenv("ENPHASE_GATEWAY_SERIAL", "")
ENPHASE_GATEWAY_PORT = int(os.getenv("ENPHASE_GATEWAY_PORT", "443"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class EnphaseCollector:
    """Collects energy data from one or more Enphase gateways."""
    
    def __init__(
        self,
        gateways: list[Dict[str, str]],
        enlighten_email: str = "",
        enlighten_password: str = "",
        token_cache_dir: str = "/tmp"
    ):
        """
        Initialize collector for multiple gateways.
        
        Args:
            gateways: List of gateway dicts from discover_gateways()
                Each dict: {'host': str, 'serial': str, 'ip': str}
            enlighten_email: Enlighten portal email
            enlighten_password: Enlighten portal password
            token_cache_dir: Directory for token caches
        """
        self.gateways = gateways
        self.session = requests.Session()
        self.session.verify = False
        
        # Create token manager for each gateway
        self.token_managers = {}
        
        if ENPHASE_TOKEN_AVAILABLE:
            for gw in gateways:
                cache_file = os.path.join(token_cache_dir, f"enphase_token_{gw['serial']}.json")
                tm = EnphaseTokenManager(
                    gateway_serial=gw['serial'],
                    token_cache_file=cache_file,
                    enlighten_email=enlighten_email,
                    enlighten_password=enlighten_password,
                    gateway_host=gw['host']
                )
                self.token_managers[gw['serial']] = tm
                logger.info(f"Token manager for {gw['host']} (serial: {gw['serial']})")
        else:
            logger.warning("enphase_token module not available - authentication disabled")
        
    def get_current_readings(self) -> list[Dict[str, Any]]:
        """
        Fetch current energy readings from all gateways.
        
        Returns:
            List of reading dicts, one per gateway with keys:
            - gateway_host: Gateway hostname
            - gateway_serial: Gateway serial
            - solar_production_w, grid_consumption_w, etc.
            Empty list if all requests fail
        """
        all_readings = []
        
        for gw in self.gateways:
                try:
                    # Get authentication token for this gateway
                    headers = {}
                    token_manager = self.token_managers.get(gw['serial'])
                    
                    if token_manager:
                        token = token_manager.get_token()
                        if token:
                            headers['Authorization'] = f'Bearer {token}'
                            logger.debug(f"Using token for {gw['host']}")
                    
                    # Try production endpoint (works with or without production meter)
                    url = f"https://{gw['host']}/ivp/pdm/energy"
                    response = self.session.get(url, headers=headers, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        reading = self._parse_readings(data)
                        reading['gateway_host'] = gw['host']
                        reading['gateway_serial'] = gw['serial']
                        all_readings.append(reading)
                        logger.debug(f"Got reading from {gw['host']}")
                    elif response.status_code == 401 or response.status_code == 403:
                        logger.warning(f"Auth failed for {gw['host']} - refreshing token...")
                        if token_manager:
                            token_data = token_manager.acquire_token()
                            if token_data:
                                headers['Authorization'] = f'Bearer {token_data["token"]}'
                                response = self.session.get(url, headers=headers, timeout=5)
                                if response.status_code == 200:
                                    reading = self._parse_readings(response.json())
                                    reading['gateway_host'] = gw['host']
                                    reading['gateway_serial'] = gw['serial']
                                    all_readings.append(reading)
                    else:
                        logger.warning(f"Unexpected status {response.status_code} from {gw['host']}")
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request failed for {gw['host']}: {e}")
                except Exception as e:
                    logger.error(f"Error fetching from {gw['host']}: {e}")
        
        if all_readings:
            logger.info(f"Collected readings from {len(all_readings)}/{len(self.gateways)} gateway(s)")
        else:
            logger.warning("Failed to collect readings from any gateway")
        
        return all_readings
    
    def _parse_readings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse readings from Enphase API /ivp/pdm/energy response.
        
        The response includes:
        - production: PCU (microinverters), RGM (revenue grade meters), EIM (internal meter)
        - consumption: EIM (internal meter)
        
        Each has wattHoursToday, wattHoursSevenDays, wattHoursLifetime, wattsNow
        """
        try:
            # Extract production data (prioritize PCU/microinverters)
            production = data.get('production', {})
            pcu = production.get('pcu', {})
            
            solar_production_w = float(pcu.get('wattsNow', 0))
            solar_energy_today_wh = float(pcu.get('wattHoursToday', 0))
            solar_energy_lifetime_wh = float(pcu.get('wattHoursLifetime', 0))
            
            # Extract consumption data
            consumption = data.get('consumption', {})
            eim = consumption.get('eim', {})
            
            home_consumption_w = float(eim.get('wattsNow', 0))
            consumption_energy_today_wh = float(eim.get('wattHoursToday', 0))
            
            return {
                'solar_production_w': solar_production_w,
                'solar_energy_today_wh': solar_energy_today_wh,
                'solar_energy_lifetime_wh': solar_energy_lifetime_wh,
                'home_consumption_w': home_consumption_w,
                'consumption_energy_today_wh': consumption_energy_today_wh,
                'timestamp': datetime.utcnow().isoformat()
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse readings: {e}")
            return {}


class InfluxDBWriter:
    """Writes energy data to InfluxDB time-series database."""
    
    def __init__(self, url: str, org: str, bucket: str, token: str = ""):
        if not INFLUXDB_AVAILABLE:
            raise RuntimeError("influxdb-client library not available")
        
        self.client = InfluxDBClient(
            url=url,
            token=token if token else None,
            org=org
        )
        self.bucket = bucket
        self.org = org
        
    def write_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Write a single gateway reading to InfluxDB with gateway tags.
        
        Args:
            reading: Dictionary with energy measurements including:
                - gateway_host: Gateway hostname
                - gateway_serial: Gateway serial number
                - solar_production_w, home_consumption_w, etc.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            gateway_host = reading.get('gateway_host', 'unknown')
            gateway_serial = reading.get('gateway_serial', 'unknown')
            
            point = Point("energy_readings") \
                .tag("source", "enphase_gateway") \
                .tag("location", "home") \
                .tag("gateway_host", gateway_host) \
                .tag("gateway_serial", gateway_serial)

            for key, value in reading.items():
                if key in ["timestamp", "gateway_host", "gateway_serial"]:
                    if key == "timestamp":
                        point = point.time(value)
                    # Tags already set above
                elif isinstance(value, (int, float)):
                    point = point.field(key, value)

            with self.client.write_api() as write_api:
                write_api.write(
                    bucket=self.bucket,
                    org=self.org,
                    record=point,
                )
            
            logger.debug(f"Wrote reading from {gateway_host}: {reading.get('solar_production_w', 0)}W solar")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write to InfluxDB: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test InfluxDB connection."""
        try:
            health = self.client.ping()
            logger.info(f"InfluxDB connection OK: {health}")
            return True
        except Exception as e:
            logger.error(f"InfluxDB connection failed: {e}")
            return False


class EnergyMonitoringDaemon:
    """Main daemon orchestrating multi-gateway data collection and storage."""
    
    def __init__(
        self,
        poll_interval: int = 10,
        enlighten_email: str = "",
        enlighten_password: str = "",
        max_gateways: int = 5
    ):
        """
        Initialize daemon with automatic gateway discovery.
        
        Args:
            poll_interval: Seconds between polls
            enlighten_email: Enlighten portal email
            enlighten_password: Enlighten portal password
            max_gateways: Maximum number of gateways to discover
        """
        self.poll_interval = poll_interval
        self.running = False
        self.max_gateways = max_gateways
        
        # Check for manual gateway configuration (skip discovery if provided)
        if ENPHASE_GATEWAY_IP and ENPHASE_GATEWAY_SERIAL:
            logger.info(f"Using configured gateway: {ENPHASE_GATEWAY_IP} (serial: {ENPHASE_GATEWAY_SERIAL})")
            self.gateways = [{
                'host': ENPHASE_GATEWAY_IP,
                'serial': ENPHASE_GATEWAY_SERIAL,
                'ip': ENPHASE_GATEWAY_IP,
                'model': 'configured',
                'software': 'unknown'
            }]
        else:
            # Discover gateways on local network
            logger.info("Discovering Enphase gateways...")
            self.gateways = EnphaseTokenManager.discover_gateways(max_gateways=max_gateways)
        
        if not self.gateways:
            logger.error("No gateways discovered. Exiting.")
            logger.error("TIP: Set ENPHASE_GATEWAY_IP and ENPHASE_GATEWAY_SERIAL in .env to skip discovery")
            raise RuntimeError("No Enphase gateways found on local network")
        
        # Initialize collector for all discovered gateways
        self.collector = EnphaseCollector(
            gateways=self.gateways,
            enlighten_email=enlighten_email,
            enlighten_password=enlighten_password,
            token_cache_dir=ENPHASE_TOKEN_CACHE_DIR
        )
        self.influxdb: Optional[InfluxDBWriter] = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, stopping...")
        self.running = False
    
    def initialize_influxdb(self) -> bool:
        """Initialize InfluxDB connection."""
        if not INFLUXDB_AVAILABLE:
            logger.error("InfluxDB client library not available. "
                        "Install: pip install influxdb-client")
            return False
        
        try:
            self.influxdb = InfluxDBWriter(
                url=INFLUXDB_URL,
                org=INFLUXDB_ORG,
                bucket=INFLUXDB_BUCKET,
                token=INFLUXDB_TOKEN
            )
            
            if self.influxdb.test_connection():
                logger.info("InfluxDB initialized successfully")
                return True
            else:
                logger.error("InfluxDB health check failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize InfluxDB: {e}")
            return False
    
    def run_once(self) -> bool:
        """
        Run a single collection cycle for all gateways.
        
        Returns:
            True if successful, False otherwise
        """
        # Fetch readings from all gateways
        all_readings = self.collector.get_current_readings()
        
        if not all_readings:
            logger.warning("Failed to fetch readings from any gateway")
            return False
        
        # Aggregate and calculate derived metrics
        total_solar_production = sum(r.get('solar_production_w', 0) for r in all_readings)
        total_home_consumption = sum(r.get('home_consumption_w', 0) for r in all_readings)
        total_grid_export = sum(r.get('grid_export_w', 0) for r in all_readings)
        
        # Calculate derived metrics for each gateway
        for reading in all_readings:
            # Self-consumption
            reading['self_consumption_w'] = (
                reading.get('solar_production_w', 0) - reading.get('grid_export_w', 0)
            )
            
            # Self-consumption ratio
            home_consumption = reading.get('home_consumption_w', 0)
            if home_consumption > 0:
                reading['self_consumption_ratio'] = (
                        reading.get('self_consumption_w', 0) / home_consumption
                    )
            else:
                reading['self_consumption_ratio'] = 0.0
            
            # Store to InfluxDB
            if self.influxdb:
                if not self.influxdb.write_reading(reading):
                    logger.error(f"Failed to write reading from {reading.get('gateway_host', 'unknown')}")
        
        # Log summary (aggregate)
        logger.info(
            f"Aggregated: Solar {total_solar_production:.0f}W | "
            f"Consumption {total_home_consumption:.0f}W | "
            f"Export {total_grid_export:+.0f}W | "
            f"Gateways: {len(all_readings)}"
        )
        
        return True
    
    def run(self):
        """Main daemon loop."""
        logger.info("Starting multi-gateway Enphase collector daemon...")
        logger.info(f"Gateways discovered: {len(self.gateways)}")
        for gw in self.gateways:
            logger.info(f"  - {gw['host']} (serial: {gw['serial']})")
        logger.info(f"Poll interval: {self.poll_interval}s")
        
        # Initialize InfluxDB
        if not self.initialize_influxdb():
            logger.error("Failed to initialize InfluxDB. Exiting.")
            return
        
        self.running = True
        logger.info("Daemon running. Press Ctrl+C to stop.")
        
        consecutive_failures = 0
        max_failures = 5
        
        while self.running:
            try:
                if self.run_once():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    
                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many consecutive failures ({consecutive_failures}). Stopping.")
                        break
                
                # Wait for next poll
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                consecutive_failures += 1
        
        logger.info("Daemon stopped.")


def main():
    """Entry point for daemon with automatic gateway discovery."""
    parser = argparse.ArgumentParser(
        description="Enphase Gateway Data Collector Daemon (Multi-Gateway)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--max-gateways',
        type=int,
        default=5,
        help='Maximum number of gateways to auto-discover (default: 5)'
    )
    
    parser.add_argument(
        '--enlighten-email',
        default=ENLIGHTEN_EMAIL,
        help='Enlighten portal email (optional: ENLIGHTEN_EMAIL)'
    )
    
    parser.add_argument(
        '--enlighten-password',
        default=ENLIGHTEN_PASSWORD,
        help='Enlighten portal password (optional: ENLIGHTEN_PASSWORD)'
    )
    
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=POLL_INTERVAL_SECONDS,
        help=f'Polling interval in seconds (default: {POLL_INTERVAL_SECONDS})'
    )
    
    parser.add_argument(
        '--influxdb-url',
        default=INFLUXDB_URL,
        help=f'InfluxDB URL (default: {INFLUXDB_URL})'
    )
    
    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Test gateway connection and exit'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Fetch readings but don't store to InfluxDB"
    )
    
    args = parser.parse_args()
    
    # Create daemon with auto-discovery
    daemon = EnergyMonitoringDaemon(
        poll_interval=args.poll_interval,
        enlighten_email=args.enlighten_email,
        enlighten_password=args.enlighten_password,
        max_gateways=args.max_gateways
    )
    
    # Test mode
    if args.test_connection:
        logger.info("Testing gateway connection...")
        readings = daemon.collector.get_current_readings()
        
        if readings:
            print(json.dumps(readings, indent=2))
            print(f"\n✅ Successfully connected to {len(readings)} gateway(s)!")
            return 0
        else:
            print("\n❌ Failed to connect to gateway")
            return 1
    
    # Dry run mode
    if args.dry_run:
        logger.info("Dry run mode - fetching readings without storing...")
        if daemon.run_once():
            print("\n✅ Dry run successful!")
            return 0
        else:
            print("\n❌ Dry run failed")
            return 1
    
    # Normal daemon mode
    daemon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
