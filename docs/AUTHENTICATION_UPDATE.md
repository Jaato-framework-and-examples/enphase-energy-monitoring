# Authentication Update - Optional Parameters

## Summary

Updated `enphase_token.py` and `enphase_collector.py` to support **optional** command-line parameters with defaults loaded from `.env` file. Previously, `--serial` was required; now all parameters are optional and can be configured via environment variables.

## Changes Made

### 1. `enphase_token.py`

**Added Parameters:**
- `--serial` (now optional, defaults to `ENPHASE_GATEWAY_SERIAL` from `.env`)
- `--enlighten-email` (optional, defaults to `ENLIGHTEN_EMAIL` from `.env`)
- `--enlighten-password` (optional, defaults to `ENLIGHTEN_PASSWORD` from `.env`)

**Features:**
- Loads `.env` file automatically before parsing arguments
- Validates that serial number is provided (via argument or `.env`)
- Warns if Enlighten credentials missing (auto-fetch will attempt, then prompt)
- Supports manual token entry as fallback

**Usage:**
```bash
# All parameters from .env
python3 enphase_token.py

# Override specific parameter
python3 enphase_token.py --serial 1234567890AB

# Override credentials
python3 enphase_token.py --enlighten-email user@example.com --enlighten-password secret

# Test cached token only
python3 enphase_token.py --test-only
```

### 2. `enphase_collector.py`

**Added Parameters:**
- `--enlighten-email` (optional, defaults to `ENLIGHTEN_EMAIL` from `.env`)
- `--enlighten-password` (optional, defaults to `ENLIGHTEN_PASSWORD` from `.env`)

**Existing Parameters:**
- `--gateway-ip` (defaults to `ENPHASE_GATEWAY_IP`)
- `--gateway-serial` (defaults to `ENPHASE_GATEWAY_SERIAL`)
- `--gateway-port` (defaults to `ENPHASE_GATEWAY_PORT`)
- `--token-cache` (defaults to `ENPHASE_TOKEN_CACHE`)

**Features:**
- Loads `.env` file automatically
- Passes Enlighten credentials to `EnphaseTokenManager`
- Credentials are optional - system will attempt anonymous fetch, then prompt

**Usage:**
```bash
# All parameters from .env
python3 enphase_collector.py

# Test connection
python3 enphase_collector.py --test-connection

# Dry run (fetch without storing)
python3 enphase_collector.py --dry-run

# Override specific parameter
python3 enphase_collector.py --gateway-ip 192.168.50.42

# Override credentials
python3 enphase_collector.py --enlighten-email user@example.com --enlighten-password secret
```

## Environment Variables

The `.env` file is the single source of truth for configuration:

```bash
# Required for authentication
ENPHASE_GATEWAY_SERIAL=122140070291

# Optional: Enable automatic token acquisition from Enlighten portal
ENLIGHTEN_EMAIL=dani.apanoia@gmail.com
ENLIGHTEN_PASSWORD=your_password_here

# Optional: Gateway configuration
ENPHASE_GATEWAY_IP=192.168.50.42
ENPHASE_GATEWAY_PORT=80
ENPHASE_TOKEN_CACHE=/tmp/enphase_token.json
```

## Authentication Flow

### With Enlighten Credentials (Recommended)
1. System logs in to Enlighten portal automatically
2. Fetches token from: `https://enlighten.enphaseenergy.com/entrez-auth-token?serial_num=<SN>`
3. Caches token locally for 1 year
4. Uses token for all API requests
5. Auto-refreshes when token expires

### Without Enlighten Credentials (Fallback)
1. System attempts anonymous fetch from Enlighten
2. If that fails, prompts for manual token entry
3. You can manually visit: `https://enlighten.enphaseenergy.com/entrez-auth-token?serial_num=<SN>`
4. Copy token and paste into prompt
5. Token is cached and used automatically

## Benefits

✅ **No required parameters** - All can be set in `.env`
✅ **Secure defaults** - Credentials stored in `.env`, not command line
✅ **Automatic token acquisition** - No manual intervention needed
✅ **Single source of truth** - `.env` file contains all configuration
✅ **Backward compatible** - Still works with command-line arguments
✅ **Test mode** - Verify credentials before running daemon

## Testing

To verify setup:
```bash
# Test token acquisition
python3 enphase_token.py --serial 122140070291 --test-only

# Test gateway connection
python3 enphase_collector.py --test-connection

# Dry run to see data
python3 enphase_collector.py --dry-run
```

---

**Version:** 1.1.0
**Date:** 2025-02-14
**Status:** ✅ Complete
