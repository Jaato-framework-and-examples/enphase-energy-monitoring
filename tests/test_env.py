#!/usr/bin/env python3
"""Test script to verify environment variable loading."""

import os
import sys

def load_env_vars():
    """Load environment variables from .env file."""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    env_vars = {}
    
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
                    # Set as environment variable
                    os.environ[key.strip()] = value.strip()
    
    return env_vars

# Load environment variables
env_vars = load_env_vars()

print("Environment variables loaded:")
for key, value in env_vars.items():
    if 'PASSWORD' not in key:  # Don't print passwords
        print(f"  {key} = {value}")

# Test enphase_token.py
print("\nTesting enphase_token.py help:")
os.system("python3 enphase_token.py --help | grep -A2 'serial'")

# Test enphase_collector.py
print("\nTesting enphase_collector.py help:")
os.system("python3 enphase_collector.py --help | grep -A2 'enlighten'")
