#!/usr/bin/env python3
"""
Test script for Jaato Energy Advisor

Validates:
1. Jaato SDK is installed and working
2. Jaato server connection
3. InfluxDB connectivity
4. Agent configurations
5. Basic analysis workflow
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from jaato_advisor import (
        JaatoEnergyAdvisor,
        JaatoClientWrapper,
        InfluxDBFetcher,
        PriceEstimator,
        EnergyContext
    )
    from jaato_agents_config import (
        get_agent_config,
        list_agents,
        AGENT_REGISTRY
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the tests/ directory")
    sys.exit(1)


def test_imports():
    """Test that all required modules can be imported."""
    print("\n" + "="*60)
    print("Testing Imports...")
    print("="*60)

    try:
        import jaato_sdk
        print("✓ jaato-sdk imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import jaato-sdk: {e}")
        return False

    try:
        import influxdb_client
        print("✓ influxdb-client imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import influxdb-client: {e}")
        return False

    return True


def test_agent_configs():
    """Test agent configurations."""
    print("\n" + "="*60)
    print("Testing Agent Configurations...")
    print("="*60)

    agents = list_agents()
    print(f"✓ Found {len(agents)} agent configurations")

    for agent_name in agents:
        config = get_agent_config(agent_name)
        print(f"\n  Agent: {agent_name}")
        print(f"    Description: {config.description}")
        print(f"    Temperature: {config.temperature}")
        print(f"    Tools: {len(config.tools)}")
        print(f"    Memory: {config.memory_enabled}")

    return True


def test_price_estimator():
    """Test price estimation logic."""
    print("\n" + "="*60)
    print("Testing Price Estimator...")
    print("="*60)

    estimator = PriceEstimator()

    # Test a few hours
    test_hours = [0, 8, 10, 14, 18, 22]
    for hour in test_hours:
        period = estimator.get_period(hour)
        price = estimator.get_price(hour)
        print(f"  {hour:02d}:00 → {period:5s} @ €{price:.2f}/kWh")

    return True


def test_energy_context():
    """Test energy context creation."""
    print("\n" + "="*60)
    print("Testing Energy Context...")
    print("="*60)

    context = EnergyContext(
        current_consumption_w=1500.0,
        current_production_w=3500.0,
        grid_import_w=0.0,
        grid_export_w=2000.0,
        current_hour=14,
        current_price_eur_kwh=0.15,
        price_period="flat"
    )

    print(f"  Consumption: {context.current_consumption_w} W")
    print(f"  Production: {context.current_production_w} W")
    print(f"  Net export: {context.grid_export_w} W")
    print(f"  Price period: {context.price_period}")

    return True


async def test_jaato_connection():
    """Test connection to jaato server."""
    print("\n" + "="*60)
    print("Testing Jaato Server Connection...")
    print("="*60)

    try:
        client = JaatoClientWrapper()
        print("  Attempting to connect to jaato server...")

        connected = await client.connect()

        if connected:
            print("✓ Connected to jaato server")
            print(f"  Socket: {client.socket_path}")
            print(f"  State: {client.connection_state}")

            await client.disconnect()
            return True
        else:
            print("❌ Failed to connect to jaato server")
            print("  Make sure jaato server is running:")
            print("    $ jaato server")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


async def test_influxdb_connection():
    """Test connection to InfluxDB."""
    print("\n" + "="*60)
    print("Testing InfluxDB Connection...")
    print("="*60)

    try:
        fetcher = InfluxDBFetcher(
            url="http://localhost:8086",
            token=""
        )
        print("  Attempting to query InfluxDB...")

        readings = await fetcher.get_current_readings()

        print("✓ InfluxDB query successful")
        print(f"  Consumption: {readings['consumption']:.1f} W")
        print(f"  Production: {readings['production']:.1f} W")
        print(f"  Import: {readings['import']:.1f} W")
        print(f"  Export: {readings['export']:.1f} W")

        return True

    except Exception as e:
        print(f"❌ InfluxDB error: {e}")
        print("  Make sure InfluxDB is running:")
        print("    $ docker-compose up -d influxdb")
        return False


async def test_advisor_initialization():
    """Test full advisor initialization."""
    print("\n" + "="*60)
    print("Testing Advisor Initialization...")
    print("="*60)

    try:
        advisor = JaatoEnergyAdvisor(
            jaato_socket="/tmp/jaato.sock",
            influxdb_url="http://localhost:8086"
        )

        print("  Initializing advisor...")
        initialized = await advisor.initialize()

        if initialized:
            print("✓ Advisor initialized successfully")

            # Test context building
            print("  Building energy context...")
            context = await advisor.build_context()

            print(f"✓ Context built:")
            print(f"  Current consumption: {context.current_consumption_w:.0f} W")
            print(f"  Current production: {context.current_production_w:.0f} W")
            print(f"  Price period: {context.price_period}")

            await advisor.stop()
            return True
        else:
            print("❌ Failed to initialize advisor")
            await advisor.stop()
            return False

    except Exception as e:
        print(f"❌ Advisor error: {e}")
        return False


async def run_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Jaato Energy Advisor Test Suite")
    print("="*60)

    results = []

    # Sync tests
    results.append(("Imports", test_imports()))
    results.append(("Agent Configs", test_agent_configs()))
    results.append(("Price Estimator", test_price_estimator()))
    results.append(("Energy Context", test_energy_context()))

    # Async tests
    results.append(("Jaato Connection", await test_jaato_connection()))
    results.append(("InfluxDB Connection", await test_influxdb_connection()))
    results.append(("Advisor Initialization", await test_advisor_initialization()))

    # Summary
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(run_tests()))
