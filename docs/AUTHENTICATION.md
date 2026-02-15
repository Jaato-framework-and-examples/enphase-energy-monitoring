# Enphase API Authentication Guide

## 🎉 Update: Optional Parameters with .env Support

**Good news:** All authentication parameters are now **optional** at the command line! You can configure everything in your `.env` file and simply run:

```bash
python3 enphase_token.py
```

The script will automatically load credentials from `.env` and fetch your token.

---

## 🚀 Quick Start

### Step 1: Configure `.env`

Add your gateway serial and Enlighten credentials to `.env`:

```bash
# Required: Gateway serial number
ENPHASE_GATEWAY_SERIAL=122140070291

# Optional: Enlighten credentials for automatic token acquisition
ENLIGHTEN_EMAIL=your_email@example.com
ENLIGHTEN_PASSWORD=your_password
```

### Step 2: Run Token Manager

```bash
# All parameters from .env
python3 enphase_token.py

# Or test existing cached token
python3 enphase_token.py --test-only
```

That's it! The system will:
1. Log in to Enlighten portal automatically
2. Fetch your authentication token
3. Cache it locally for 1 year
4. Use it for all API requests

---

## 📋 Prerequisites

1. **Gateway Serial Number**: Found on:
   - Sticker on your gateway (bottom/side)
   - Enlighten mobile app → Menu → System → Serial Number
   - Gateway web UI → About → Serial Number

2. **Enphase Enlighten Account** (optional but recommended): Create at https://enlighten.enphaseenergy.com/

---

## 🔐 How Authentication Works

Your Enphase gateway requires an **authentication token** to access most local API endpoints. This token is obtained from Enphase's Enlighten portal and must be provided with API requests.

## 📋 Prerequisites

1. **Gateway Serial Number**: Found on:
   - Sticker on your gateway (bottom/side)
   - Enlighten mobile app → Menu → System → Serial Number
   - Gateway web UI → About → Serial Number

2. **Enphase Enlighten Account**: Create at https://enlighten.enphaseenergy.com/

## 🔑 Obtaining Your Authentication Token

**Good news:** Tokens are acquired **automatically** from the Enlighten portal!

The system fetches tokens directly from:
```
https://enlighten.enphaseenergy.com/entrez-auth-token?serial_num=<YOUR_SERIAL>
```

No manual interaction required - just provide your gateway serial number and the system does the rest.

### Prerequisites

Find your gateway **serial number** (required for token acquisition):
- Sticker on your gateway (bottom/side)
- Enlighten mobile app → Menu → System → Serial Number
- Gateway web UI → About → Serial Number

### How Automatic Acquisition Works

1. System requests token from Enlighten portal using your gateway serial
2. Enlighten returns token as plain text (32-character hex string)
3. Token is validated, cached locally, and used automatically
4. Token expires after 1 year - system auto-refreshes

**No login required** - the Enlighten token endpoint provides tokens directly when accessed with a valid serial number.

## 📁 How Token Is Stored

Tokens are cached locally at `/tmp/enphase_token.json` (configurable):

```json
{
  "token": "1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6",
  "serial": "1234567890AB",
  "acquired_at": "2025-02-14T12:00:00",
  "expires_at": "2026-02-14T12:00:00"
}
```

**Security Notes:**
- Token is valid for **1 year** from acquisition
- File is readable only by user in Docker container
- Never commit `.env` or token cache to version control

## 🧪 Testing Authentication

### Test Token Acquisition

```bash
cd enphase_monitoring

# Test automatic token acquisition
docker exec enphase_collector python3 /app/enphase_token.py \
  --serial 1234567890AB \
  --gateway-ip 192.168.50.42
```

Expected output:
```
✅ Successfully acquired token from Enlighten
   Serial: 1234567890AB
   Expires: 2026-02-14T12:00:00
```

The token is automatically fetched from Enlighten - **no manual input required!**

### Test with Collector

```bash
# Test connection with authentication
docker exec enphase_collector python3 /app/enphase_collector.py \
  --gateway-ip 192.168.50.42 \
  --gateway-serial 1234567890AB \
  --test-connection
```

## 🔁 Token Refresh

Tokens expire after **1 year**. The system handles this:

1. **Expiration Detection:**
   - On each request, 401/403 status codes trigger refresh
   - Cached token expiration date is checked

2. **Refresh Process:**
   - You'll be prompted for new token
   - Update happens automatically
   - Daemon continues without interruption

3. **Manual Refresh:**
   ```bash
   # Remove cached token to force re-acquisition
   rm /tmp/enphase_token.json
   
   # Re-run daemon - will prompt for token
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|-----------|-----------|----------|-------------|
| `ENPHASE_GATEWAY_IP` | ✅ Yes | - | Gateway IP address |
| `ENPHASE_GATEWAY_PORT` | No | 80 | Gateway port |
| `ENPHASE_GATEWAY_SERIAL` | ✅ Yes | - | Gateway serial number |
| `ENPHASE_TOKEN_CACHE` | No | `/tmp/enphase_token.json` | Token cache path |
| `ENLIGHTEN_EMAIL` | No | - | For auto-refresh (future) |
| `ENLIGHTEN_PASSWORD` | No | - | For auto-refresh (future) |

### Docker Compose

```yaml
services:
  enphase_collector:
    environment:
      - ENPHASE_GATEWAY_IP=192.168.50.42
      - ENPHASE_GATEWAY_SERIAL=1234567890AB
      - ENPHASE_TOKEN_CACHE=/app/data/token.json
    volumes:
      - ./data:/app/data  # Persist token cache
```

## 🐛 Troubleshooting

### "Authentication Failed" (401/403)

**Cause:** Invalid or expired token

**Solution:**
```bash
# Clear cached token
rm /tmp/enphase_token.json

# Re-acquire
docker exec enphase_collector python3 /app/enphase_token.py \
  --serial 1234567890AB
```

### "No Serial Number Provided"

**Cause:** Missing `ENPHASE_GATEWAY_SERIAL`

**Solution:**
```bash
# Set in .env
echo "ENPHASE_GATEWAY_SERIAL=1234567890AB" >> .env

# Or pass as argument
docker exec enphase_collector python3 /app/enphase_collector.py \
  --gateway-serial 1234567890AB
```

### "Token Format Invalid"

**Cause:** Incorrect token format (not 32-char hex)

**Solution:**
- Ensure you copied the full token (no spaces)
- Token should be 32 hexadecimal characters
- Check you're using the right serial number

### Token Works but Some Endpoints Fail

**Cause:** Different Enphase models use different API endpoints

**Solution:**
- Check your gateway model in Enlighten app
- Adjust `EnphaseCollector._parse_readings()` for your model
- Consult Enphase API documentation for your gateway

## 🔒 Security Best Practices

1. **Never commit tokens to Git:**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo "/tmp/enphase_token.json" >> .gitignore
   echo "*.json.bak" >> .gitignore
   ```

2. **Use Docker secrets in production:**
   ```yaml
   services:
     enphase_collector:
       secrets:
         - enphase_token
   ```

3. **Restrict file permissions:**
   ```bash
   chmod 600 /tmp/enphase_token.json
   ```

4. **Rotate tokens annually:**
   - Set calendar reminder for token expiration
   - Test new token before old one expires

5. **Monitor authentication failures:**
   - Check logs for 401/403 errors
   - Set up alerts for repeated auth failures

## 📚 Additional Resources

- **Enphase Enlighten Portal:** https://enlighten.enphaseenergy.com/
- **Enphase API Docs:** https://enphase.com/api-docs (if available)
- **Main Documentation:** See README.md and SYSTEM.md

## ❓ FAQ

**Q: Can I use the same token for multiple gateways?**
A: No, tokens are bound to specific serial numbers.

**Q: How often do I need to refresh the token?**
A: Every 1 year. You'll be prompted automatically when needed.

**Q: Can I skip authentication?**
A: Some endpoints work without auth, but most require it. You'll get 401/403 errors without it.

**Q: Is my token sent to external servers?**
A: No, authentication is handled locally with your Enphase gateway. No data leaves your network.

**Q: What if I lose access to my Enlighten account?**
A: Your cached token continues working until it expires. After expiration, you'll need account access to get a new token.

---

**Version:** 1.1.0  
**Last Updated:** 2025-02-14  
**Status:** ✅ Production Ready
