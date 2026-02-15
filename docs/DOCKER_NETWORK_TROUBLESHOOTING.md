# Docker Network Configuration for Gateway Discovery

## Problem: "No Enphase gateways found on local network"

If you see this error when running the container, it's because the gateway discovery relies on mDNS/Bonjour hostname resolution (e.g., `envoy.local`), which doesn't work in Docker's default bridge network mode.

## Two Solutions

### Option 1: Use Host Network (Recommended for Discovery)

The `docker-compose.yml` is configured with `network_mode: host`, which gives the container access to your host's network. This allows mDNS discovery to work.

```yaml
enphase_collector:
  network_mode: host  # Required for mDNS/Bonjour discovery
```

**Pros:**
- Automatic gateway discovery works
- No manual configuration needed
- Simplest setup

**Cons:**
- Container uses host network directly
- InfluxDB URL must be `http://localhost:8086` instead of `http://influxdb:8086`

### Option 2: Manual Gateway Configuration

If you prefer to use bridge networking (or host mode isn't available), you can manually configure your gateway:

1. **Find your gateway IP address:**
   - Check your router's DHCP client list
   - Or use the Enlighten mobile app
   - Or ping `envoy.local` from your host machine

2. **Find your gateway serial number:**
   - Check the sticker on your gateway
   - Or find it in the Enlighten web portal

3. **Edit `.env` file:**
   ```bash
   ENPHASE_GATEWAY_IP=192.168.1.100
   ENPHASE_GATEWAY_SERIAL=1234567890AB
   ENPHASE_GATEWAY_PORT=443
   ```

4. **If using bridge mode, update `docker-compose.yml`:**
   - Remove or comment out `network_mode: host`
   - Uncomment the `networks:` section
   - Update `INFLUXDB_URL` back to `http://influxdb:8086`

**Pros:**
- Works with any network mode
- More isolation between container and host
- Reliable - no dependency on mDNS

**Cons:**
- Requires manual IP configuration
- IP address may change if using DHCP (consider static IP or DHCP reservation)

## Testing Gateway Discovery

From your host machine (not inside Docker), you can test if mDNS resolution works:

```bash
# Test if envoy.local resolves
ping envoy.local

# Or check all Enphase devices on network
nslookup envoy.local
dig envoy.local
```

If these commands fail from your host, you may need to:
- Install Avahi/Bonjour services on your host OS
- Check that your router supports mDNS forwarding
- Use Option 2 (manual configuration) instead

## Network Mode Comparison

| Feature | Bridge (default) | Host Mode |
|---------|------------------|-----------|
| Container IP | Separate subnet | Shares host IP |
| Service discovery | Works via DNS names | Uses localhost |
| mDNS support | ❌ No | ✅ Yes |
| Gateway auto-discovery | ❌ No | ✅ Yes |
| Manual gateway config | ✅ Yes | ✅ Yes |
| Network isolation | ✅ Yes | ❌ No |

## Recommendation

**For most users:** Use `network_mode: host` (Option 1) with automatic discovery. This is the simplest and most reliable approach for home monitoring setups.

**For advanced users:** Use bridge networking with manual gateway configuration (Option 2) if you need better network isolation or are running in an environment where host networking isn't available.
