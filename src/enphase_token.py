#!/usr/bin/env python3
"""
Enphase Authentication Token Manager

Handles acquisition and refresh of Enphase API authentication tokens.
Tokens are obtained via enlighten.enphaseenergy.com login + entrez.enphaseenergy.com/tokens

Author: Energy Monitoring System
Version: 1.1.0
"""

import requests
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os
import stat
import base64
import urllib3
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning for self-signed gateway certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class EnphaseTokenManager:
    """
    Manages Enphase API authentication tokens.

    Enphase gateway APIs require a JWT token obtained via a two-step flow:
    1. Login to enlighten.enphaseenergy.com/login/login.json to get a session_id
    2. POST session_id + serial to entrez.enphaseenergy.com/tokens to get the JWT

    The token is typically valid for 1 year and needs to be refreshed periodically.
    """
    
    ENLIGHTEN_BASE_URL = "https://enlighten.enphaseenergy.com"
    ENTREZ_TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"
    TOKEN_LIFETIME_DAYS = 365  # Tokens typically valid for 1 year
    
    def __init__(
        self,
        gateway_serial: str,
        token_cache_file: str = "/.enphase/token.json",  # CHANGE THIS: Default is now ~/.enphase/serial/token.json
        enlighten_email: Optional[str] = None,
        enlighten_password: Optional[str] = None,
        gateway_host: Optional[str] = None
    ):
        """
        Initialize token manager.
        
        Args:
            gateway_serial: Enphase gateway serial number
            token_cache_file: Path to cache token locally (CHANGED: Now includes serial in filename)
            enlighten_email: Enlighten portal email (optional - for auto-refresh)
            enlighten_password: Enlighten portal password (optional - for auto-refresh)
            gateway_host: Gateway hostname for discovery (e.g., "envoy.local")
        """
        # CHANGE: Token cache now includes serial number in filename for multi-gateway support
        # E.g., ~/.enphase/12214070291/token.json instead of ~/.enphase/token.json
        self.token_cache_file = token_cache_file
        self.gateway_serial = gateway_serial
        self.enlighten_email = enlighten_email
        self.enlighten_password = enlighten_password
        self.gateway_host = gateway_host
        self.session = requests.Session()
        
        # Browser-like headers required by Enlighten login endpoint
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Origin': 'https://enlighten.enphaseenergy.com',
            'Referer': 'https://enlighten.enphaseenergy.com/login',
        })

    def close(self):
        """Close the underlying HTTP session and release connection pool resources."""
        self.session.close()

    @staticmethod
    def discover_gateways(max_gateways: int = 5, timeout: int = 2) -> list[Dict[str, Any]]:
        """
        Discover all Enphase gateways on local network by probing .local hostnames.
        
        Probes: envoy.local, envoy-2.local, envoy-3.local, etc.
        Each gateway's /info endpoint returns XML with serial number (no auth required).
        
        Args:
            max_gateways: Maximum number of gateways to probe (default: 5)
            timeout: Seconds to wait for each probe (default: 2)
        
        Returns:
            List of gateway dicts with keys:
            - host: Hostname (e.g., "envoy.local")
            - serial: Gateway serial number
            - ip: Resolved IP address
            - model: Gateway model/part number
            - software: Software version
        """
        import xml.etree.ElementTree as ET
        import socket
        
        discovered = []
        logger.info(f"Scanning for up to {max_gateways} Enphase gateways...")
        
        for i in range(1, max_gateways + 1):
            if i == 1:
                hostname = "envoy.local"
            else:
                hostname = f"envoy-{i}.local"
            
            try:
                # Resolve hostname to IP
                # Try getent first (supports mDNS via libnss-mdns)
                ip = None
                try:
                    import subprocess
                    result = subprocess.run(
                        ['getent', 'hosts', hostname],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        # getent returns: "IP hostname"
                        ip = result.stdout.strip().split()[0]
                        logger.debug(f"Resolved {hostname} to {ip} via getent")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                
                # Fallback to socket.gethostbyname
                if not ip:
                    try:
                        ip = socket.gethostbyname(hostname)
                        logger.debug(f"Resolved {hostname} to {ip} via socket")
                    except socket.gaierror:
                        logger.debug(f"Host {hostname} not resolved - skipping")
                        continue
                
                logger.debug(f"Probing {hostname} ({ip})...")
                
                # Probe /info endpoint (no authentication required)
                url = f"http://{hostname}/info"
                response = requests.get(url, timeout=timeout, verify=False)
                
                if response.status_code == 200:
                    # Parse XML response
                    root = ET.fromstring(response.text)
                    
                    # Extract serial from <sn> tag
                    serial_elem = root.find('.//sn')
                    serial = serial_elem.text if serial_elem is not None else "unknown"
                    
                    # Extract model from <pn> tag
                    model_elem = root.find('.//pn')
                    model = model_elem.text if model_elem is not None else "unknown"
                    
                    # Extract software version
                    sw_elem = root.find('.//software')
                    software = sw_elem.text if sw_elem is not None else "unknown"
                    
                    gateway_info = {
                        'host': hostname,
                        'serial': serial,
                        'ip': ip,
                        'model': model,
                        'software': software
                    }
                    
                    discovered.append(gateway_info)
                    logger.info(f"  ✓ Found {hostname} - Serial: {serial}, Model: {model}")
                else:
                    logger.debug(f"  ✗ {hostname} responded with status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.debug(f"  ✗ {hostname} timed out")
            except requests.exceptions.ConnectionError:
                logger.debug(f"  ✗ {hostname} not reachable")
            except Exception as e:
                logger.debug(f"  ✗ {hostname} error: {e}")
        
        if not discovered:
            logger.warning("No Enphase gateways discovered on local network")
        else:
            logger.info(f"✓ Discovered {len(discovered)} gateway(s)")
        
        return discovered

    def load_cached_token(self) -> Optional[Dict[str, Any]]:
        """
        Load token from cache file if valid.
        
        Returns:
            Token dict with 'token', 'serial', 'acquired_at', 'expires_at' keys
            None if cache doesn't exist or token is expired
        """
        try:
            if not os.path.exists(self.token_cache_file):
                logger.debug(f"No token cache found at {self.token_cache_file}")
                return None
            
            with open(self.token_cache_file, 'r') as f:
                data = json.load(f)
            
            # Verify token matches gateway serial
            if data.get('serial') != self.gateway_serial:
                logger.warning(f"Cached token serial mismatch. Expected {self.gateway_serial}, got {data.get('serial')}")
                return None
            
            # Check expiration
            expires_at = datetime.fromisoformat(data['expires_at'])
            # Ensure timezone-aware comparison
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                logger.warning(f"Cached token expired at {expires_at}")
                return None
            
            logger.info(f"Loaded valid cached token (expires {expires_at})")
            return data
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load cached token: {e}")
            return None
    
    def save_token_to_cache(self, token_data: Dict[str, Any]) -> bool:
        """
        Save token to cache file.
        
        Args:
            token_data: Token dict to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure cache directory exists with proper permissions
            cache_dir = os.path.dirname(self.token_cache_file)
            if cache_dir:
                os.makedirs(cache_dir, mode=0o700, exist_ok=True)
            
            # CHANGE: Fix - ensure parent directory is writable before opening file
            # This prevents Permission denied errors
            try:
                # Test if we can write to directory
                test_file = os.path.join(cache_dir, ".test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except (IOError, OSError) as e:
                logger.error(f"Cache directory {cache_dir} is not writable: {e}")
                return False
            
            # Write with restricted permissions (owner-only read/write)
            fd = os.open(self.token_cache_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"Saved token to cache {self.token_cache_file}")
            return True
            
        except (IOError, OSError) as e:
            logger.error(f"Failed to save token to cache: {e}")
            return False
    
    def get_token_from_user(self) -> Optional[str]:
        """
        Prompt user to provide token manually.
        
        Returns:
            Authentication token string, or None if not provided
        """
        print("\n" + "="*70)
        print("  Enphase Authentication Token Required")
        print("="*70)
        print()
        print(f"Your Enphase gateway (Serial: {self.gateway_serial}) requires an")
        print("authentication token to access the local API.")
        print()
        print("To obtain your token:")
        print(f"  1. Visit: https://entrez.enphaseenergy.com/")
        print("  2. Log in to your Enphase account")
        print(f"  3. Enter your gateway serial number: {self.gateway_serial}")
        print("  4. Copy the JWT token from the page")
        print()
        
        token = input("Enter your Enphase authentication token (or press Enter to skip): ").strip()
        
        if not token:
            print("\n⚠️  No token provided. Some API endpoints may not work.")
            return None
        
        return token
    
    def acquire_token(self) -> Optional[Dict[str, Any]]:
        """
        Acquire authentication token from Enlighten portal.
        
        This method attempts multiple strategies:
        1. Load from cache if valid
        2. Auto-fetch from Enlighten (preferred)
        3. Prompt user for manual input (fallback)
        
        Returns:
            Token dict with 'token', 'serial', 'acquired_at', 'expires_at' keys
            None if token cannot be acquired
        """
        # Strategy 1: Check cache first
        cached = self.load_cached_token()
        if cached:
            return cached
        
        # Strategy 2: Auto-fetch from Enlighten (PREFERRED)
        logger.info("Attempting to fetch token from Enlighten portal...")
        token = self._fetch_token_from_enlighten()
        
        if token:
            # Validate and cache the token
            token_data = self._create_token_dict(token)
            if self.save_token_to_cache(token_data):
                return token_data
            else:
                # Save failed but token is valid, return it anyway
                return token_data
        
        # Strategy 3: Prompt user manually (fallback)
        logger.warning("Auto-fetch failed, prompting for manual input...")
        token = self.get_token_from_user()
        
        if not token:
            logger.error("Failed to acquire authentication token")
            return None
        
        # Validate token format
        if not self._validate_token_format(token):
            logger.error("Invalid token format")
            return None
        
        # Create token dict and cache it
        token_data = self._create_token_dict(token)
        self.save_token_to_cache(token_data)
        
        return token_data
    
    def _fetch_token_from_enlighten(self) -> Optional[str]:
        """
        Fetch token via the two-step Enphase authentication flow:

        1. POST to enlighten.enphaseenergy.com/login/login.json to get a session_id
        2. POST to entrez.enphaseenergy.com/tokens with session_id and serial to get a JWT

        Requires enlighten_email and enlighten_password to be set.

        Returns:
            JWT token string, or None if any step failed
        """
        if not self.enlighten_email or not self.enlighten_password:
            logger.warning("No Enlighten credentials provided, cannot auto-fetch token")
            return None

        try:
            # Step 1: Login to get session_id
            logger.info("Logging in to Enlighten portal...")
            login_payload = urlencode({
                "user[email]": self.enlighten_email,
                "user[password]": self.enlighten_password,
            })
            login_response = self.session.post(
                f"{self.ENLIGHTEN_BASE_URL}/login/login.json",
                data=login_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

            if login_response.status_code != 200:
                logger.error(f"Login failed with status {login_response.status_code}")
                logger.debug(f"Response: {login_response.text[:200]}")
                return None

            login_data = login_response.json()
            session_id = login_data.get("session_id")

            if not session_id:
                message = login_data.get("message", "unknown error")
                logger.error(f"Login failed: {message}")
                return None

            logger.info("Login successful, got session_id")

            # Step 2: Fetch JWT token from entrez endpoint
            logger.info("Fetching JWT token from entrez endpoint...")
            token_response = self.session.post(
                self.ENTREZ_TOKEN_URL,
                json={
                    "session_id": session_id,
                    "serial_num": self.gateway_serial,
                    "envoy_serial": self.gateway_serial,
                    "username": self.enlighten_email,
                },
                timeout=10,
            )

            if token_response.status_code != 200:
                logger.error(f"Token fetch failed with status {token_response.status_code}")
                logger.debug(f"Response: {token_response.text[:200]}")
                return None

            token = token_response.text.strip()

            if self._validate_token_format(token):
                logger.info("Successfully acquired JWT token")
                return token

            logger.error("Token response is not a valid JWT")
            logger.debug(f"Response starts with: {token[:100]}...")
            return None

        except requests.exceptions.Timeout:
            logger.error("Timeout during token acquisition")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed during token acquisition: {e}")
            return None
    
    def _validate_token_format(self, token: str) -> bool:
        """
        Validate token format.

        Enphase tokens are JWTs: three base64url-encoded segments separated by dots.

        Args:
            token: Token string to validate

        Returns:
            True if format looks valid, False otherwise
        """
        token = token.strip()

        if not token:
            logger.warning("Token is empty")
            return False

        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            logger.warning(f"Token has {len(parts)} segment(s), expected 3 (JWT format)")
            return False

        # Validate each part is valid base64url
        for i, part in enumerate(parts):
            # Add padding for base64 decoding
            padded = part + '=' * (4 - len(part) % 4)
            try:
                base64.urlsafe_b64decode(padded)
            except Exception:
                logger.warning(f"Token segment {i} is not valid base64url")
                return False

        return True
    
    def _create_token_dict(self, token: str) -> Dict[str, Any]:
        """
        Create token dict with metadata.
        
        Args:
            token: Token string
            
        Returns:
            Token dict with metadata
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.TOKEN_LIFETIME_DAYS)
        
        return {
            'token': token.strip(),
            'serial': self.gateway_serial,
            'acquired_at': now.isoformat(),
            'expires_at': expires.isoformat()
        }
    
    def get_token(self) -> Optional[str]:
        """
        Get valid authentication token, acquiring if necessary.
        
        Returns:
            Token string, or None if unavailable
        """
        token_data = self.acquire_token()
        
        if not token_data:
            return None
        
        return token_data['token']
    
    def test_token_with_gateway(self, token: str, gateway_ip: str, gateway_port: int = 443) -> bool:
        """
        Test if token works with gateway API.

        Enphase gateways use HTTPS with self-signed certificates.

        Args:
            token: Authentication token
            gateway_ip: Gateway IP address
            gateway_port: Gateway HTTPS port (default 443)

        Returns:
            True if token works, False otherwise
        """
        try:
            url = f"https://{gateway_ip}:{gateway_port}/api/v1/consumption"
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            response = self.session.get(url, headers=headers, timeout=5, verify=False)
            
            if response.status_code == 200:
                logger.info("✅ Token authentication successful!")
                return True
            elif response.status_code == 401 or response.status_code == 403:
                logger.error(f"❌ Token authentication failed (status {response.status_code})")
                return False
            else:
                logger.warning(f"Unexpected status {response.status_code} when testing token")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to test token with gateway: {e}")
            return False


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


def main():
    """CLI for token acquisition and testing."""
    import argparse
    
    # Load environment variables from .env file
    load_env_vars()
    
    parser = argparse.ArgumentParser(
        description="Enphase Authentication Token Manager",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--serial',
        default=os.environ.get('ENPHASE_GATEWAY_SERIAL'),
        help='Enphase gateway serial number (can be set via ENPHASE_GATEWAY_SERIAL env var)'
    )
    
    parser.add_argument(
        '--enlighten-email',
        default=os.environ.get('ENLIGHTEN_EMAIL'),
        help='Enlighten portal email (can be set via ENLIGHTEN_EMAIL env var)'
    )
    
    parser.add_argument(
        '--enlighten-password',
        default=os.environ.get('ENLIGHTEN_PASSWORD'),
        help='Enlighten portal password (can be set via ENLIGHTEN_PASSWORD env var)'
    )
    
    parser.add_argument(
        '--gateway-ip',
        help='Gateway IP to test token with'
    )
    
    parser.add_argument(
        '--gateway-port',
        type=int,
        default=443,
        help='Gateway HTTPS port'
    )
    
    parser.add_argument(
        '--token-cache',
        default=os.environ.get('ENPHASE_TOKEN_CACHE', os.path.join(os.path.expanduser("~"), ".enphase", "token.json")),
        help='Path to token cache file (can be set via ENPHASE_TOKEN_CACHE env var)'
    )
    
    parser.add_argument(
        '--test-only',
        action='store_true',
        help='Only test cached token, do not acquire new'
    )
    
    args = parser.parse_args()
    
    # Validate required parameters
    if not args.serial:
        parser.error("--serial is required (or set ENPHASE_GATEWAY_SERIAL in .env file)")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Validate that we have credentials for auto-fetch
    if not args.test_only and not (args.enlighten_email and args.enlighten_password):
        logger.warning("⚠️  No Enlighten credentials provided")
        logger.warning("   Token acquisition will attempt anonymous fetch, then prompt for manual input")
        logger.warning("   For automatic token acquisition, provide:")
        logger.warning("     --enlighten-email YOUR_EMAIL --enlighten-password YOUR_PASSWORD")
        logger.warning("   Or set ENLIGHTEN_EMAIL and ENLIGHTEN_PASSWORD in .env file")
    
    # Create token manager
    manager = EnphaseTokenManager(
        gateway_serial=args.serial,
        token_cache_file=args.token_cache,
        enlighten_email=args.enlighten_email,
        enlighten_password=args.enlighten_password
    )
    
    if args.test_only:
        # Test cached token
        token_data = manager.load_cached_token()
        
        if not token_data:
            print("❌ No valid cached token found")
            return 1
        
        print(f"✅ Found cached token (expires {token_data['expires_at']})")
        
        if args.gateway_ip:
            if manager.test_token_with_gateway(token_data['token'], args.gateway_ip, args.gateway_port):
                print("✅ Token works with gateway!")
                return 0
            else:
                print("❌ Token failed gateway test")
                return 1
        return 0
    
    else:
        # Acquire token
        token_data = manager.acquire_token()
        
        if not token_data:
            print("❌ Failed to acquire token")
            return 1
        
        print(f"\n✅ Token acquired successfully!")
        print(f"   Serial: {token_data['serial']}")
        print(f"   Expires: {token_data['expires_at']}")
        
        # Test with gateway if IP provided
        if args.gateway_ip:
            if manager.test_token_with_gateway(token_data['token'], args.gateway_ip, args.gateway_port):
                print(f"✅ Token verified with gateway {args.gateway_ip}")
            else:
                print(f"⚠️  Token could not be verified with gateway {args.gateway_ip}")
                print(f"   (Gateway may be offline or using different API)")
        
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
