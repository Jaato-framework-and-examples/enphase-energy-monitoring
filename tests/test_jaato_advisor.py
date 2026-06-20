#!/usr/bin/env python3
"""
Test script for Jaato Energy Advisor

Validates:
1. Jaato SDK + InfluxDB client import
2. The .jaato profile-set + agent personas exist for every specialist
3. Price estimator + energy context logic
4. InfluxDB connectivity (live)
5. Advisor construct + connect + one-shot analysis (live, needs daemon)
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

WORKSPACE = Path(__file__).parent.parent

try:
    from jaato_advisor import (
        JaatoEnergyAdvisor,
        InfluxDBFetcher,
        PriceEstimator,
        EnergyContext,
        SPECIALISTS,
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Install the SDK first:  pip install -e ../jaato/jaato-sdk")
    sys.exit(1)


def test_imports():
    """Test that all required modules can be imported."""
    print("\n" + "=" * 60)
    print("Testing Imports...")
    print("=" * 60)

    try:
        from jaato_sdk import IPCClient, ClientType, EventType  # noqa: F401
        print("✓ jaato_sdk (IPCClient/ClientType/EventType) imported")
    except ImportError as e:
        print(f"❌ Failed to import jaato_sdk: {e}")
        return False

    try:
        import influxdb_client  # noqa: F401
        print("✓ influxdb-client imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import influxdb-client: {e}")
        return False

    return True


def test_profile_set():
    """Test that the profile-set + agent persona exist for every specialist."""
    print("\n" + "=" * 60)
    print("Testing Profile-Set + Agent Personas...")
    print("=" * 60)

    profiles_dir = WORKSPACE / ".jaato" / "profiles" / "zhipuai_glm-4-7"
    agents_dir = WORKSPACE / ".jaato" / "agents"

    ok = True
    for name in SPECIALISTS:
        profile = profiles_dir / f"{name}.yaml"
        base = WORKSPACE / ".jaato" / "profiles" / f"_base_{name}.yaml"
        persona = agents_dir / f"{name}.md"
        for path, label in [(profile, "profile"), (base, "base"), (persona, "persona")]:
            if path.exists():
                print(f"✓ {name} {label}: {path.relative_to(WORKSPACE)}")
            else:
                print(f"❌ {name} {label} MISSING: {path.relative_to(WORKSPACE)}")
                ok = False

    return ok


def test_price_estimator():
    """Test price estimation logic."""
    print("\n" + "=" * 60)
    print("Testing Price Estimator...")
    print("=" * 60)

    estimator = PriceEstimator()
    for hour in [0, 8, 10, 14, 18, 22]:
        period = estimator.get_period(hour)
        price = estimator.get_price(hour)
        print(f"  {hour:02d}:00 → {period:5s} @ €{price:.2f}/kWh")

    return True


def test_energy_context():
    """Test energy context creation."""
    print("\n" + "=" * 60)
    print("Testing Energy Context...")
    print("=" * 60)

    context = EnergyContext(
        current_consumption_w=1500.0,
        current_production_w=3500.0,
        grid_import_w=0.0,
        grid_export_w=2000.0,
        current_hour=14,
        current_price_eur_kwh=0.15,
        price_period="flat",
    )
    print(f"  Consumption: {context.current_consumption_w} W")
    print(f"  Production: {context.current_production_w} W")
    print(f"  Net export: {context.grid_export_w} W")
    print(f"  Price period: {context.price_period}")

    return True


async def test_influxdb_connection():
    """Test connection to InfluxDB."""
    print("\n" + "=" * 60)
    print("Testing InfluxDB Connection...")
    print("=" * 60)

    try:
        fetcher = InfluxDBFetcher(url="http://localhost:8086", token="")
        print("  Attempting to query InfluxDB...")
        readings = await fetcher.get_current_readings()
        print("✓ InfluxDB query successful")
        for k, v in readings.items():
            print(f"  {k}: {v:.1f} W")
        return True
    except Exception as e:
        print(f"❌ InfluxDB error: {e}")
        print("  Start it with:  docker-compose up -d influxdb")
        return False


async def test_advisor_analysis():
    """Test advisor construct + connect + one-shot analysis (needs daemon)."""
    print("\n" + "=" * 60)
    print("Testing Advisor Analysis (live)...")
    print("=" * 60)

    advisor = JaatoEnergyAdvisor(
        jaato_socket="/tmp/jaato.sock",
        influxdb_url="http://localhost:8086",
    )
    try:
        if not await advisor.initialize():
            print("❌ Failed to initialize advisor (daemon/provider auth?)")
            return False
        print("✓ Advisor connected")

        result = await advisor.analyze_once()
        for spec in result["specialists"]:
            status = spec["error"] or f"{len(spec['text'])} chars"
            print(f"  {spec['agent']}: {status}")
        return all(not s["error"] for s in result["specialists"])
    except Exception as e:
        print(f"❌ Advisor error: {e}")
        return False
    finally:
        await advisor.stop()


async def run_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Jaato Energy Advisor Test Suite")
    print("=" * 60)

    results = [
        ("Imports", test_imports()),
        ("Profile-Set", test_profile_set()),
        ("Price Estimator", test_price_estimator()),
        ("Energy Context", test_energy_context()),
        ("InfluxDB Connection", await test_influxdb_connection()),
        ("Advisor Analysis", await test_advisor_analysis()),
    ]

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, r in results:
        print(f"  {'✓ PASS' if r else '❌ FAIL'}: {name}")
    print(f"\nTotal: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))
