#!/usr/bin/env python3
"""
Enphase Gateway Discovery Utility

Scans local network for Enphase gateways by probing .local hostnames.
This is a standalone utility to test gateway discovery before running the collector.

Usage:
    python3 discover_gateways.py
    python3 discover_gateways.py --max-gateways 10
"""

import sys
import os
import argparse
import logging

# Add parent directory to path to import enphase_token
sys.path.insert(0, os.path.dirname(__file__))

from enphase_token import EnphaseTokenManager

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Discover Enphase gateways on local network",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--max-gateways',
        type=int,
        default=5,
        help='Maximum number of gateways to probe'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=2,
        help='Seconds to wait for each probe'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger('enphase_token').setLevel(logging.DEBUG)
    
    print("🔍 Scanning for Enphase gateways...")
    print("=" * 70)
    
    gateways = EnphaseTokenManager.discover_gateways(
        max_gateways=args.max_gateways,
        timeout=args.timeout
    )
    
    if not gateways:
        print("\n❌ No gateways discovered!")
        print("\nTroubleshooting:")
        print("  • Ensure you're on the same network as the gateways")
        print("  • Check that gateways are powered on")
        print("  • Try increasing --timeout (default: 2s)")
        print("  • Verify DNS resolution is working (try: ping envoy.local)")
        return 1
    
    print(f"\n✅ Discovered {len(gateways)} gateway(s):")
    print("=" * 70)
    
    for i, gw in enumerate(gateways, 1):
        print(f"\nGateway {i}:")
        print(f"  Hostname:  {gw['host']}")
        print(f"  IP:        {gw['ip']}")
        print(f"  Serial:    {gw['serial']}")
        print(f"  Model:     {gw['model']}")
        print(f"  Software:  {gw['software']}")
    
    print("\n" + "=" * 70)
    print("💡 Next steps:")
    print("  • Run: python3 enphase_collector.py --test-connection")
    print("  • Or start daemon: python3 enphase_collector.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
