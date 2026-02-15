# 🔌 Enphase Home Energy Monitoring System

Complete system for monitoring your Enphase solar production and grid consumption with real-time dashboards and intelligent recommendations.

## ✨ Features

- **Automatic Gateway Discovery** - Finds Enphase gateways via mDNS/Bonjour
- **Dual Deployment Modes**:
  - 🐳 **Docker mode** (Linux): Containerized with automatic mDNS support
  - 💻 **Native mode** (Linux/macOS/Windows): Runs directly on your host
- **Configurable Polling** - Default 5-minute intervals (gateway-friendly)
- **Time-Series Storage** - InfluxDB for efficient data storage
- **Beautiful Dashboards** - Grafana visualization
- **Multi-Gateway Support** - Monitor multiple Enphase installations
- **Energy Intelligence** - Optional AI-powered optimization recommendations

## 🚀 Quick Start

### Prerequisites

Copy the example configuration file and customize it:

```bash
# Copy example configuration
cp .env.example .env

# Edit with your settings
nano .env  # or use your preferred editor
```

Then choose your deployment mode:

### Option 1: Docker Mode (Linux)

```bash
# Clone and setup
git clone <your-repo>
cd enphase_monitoring
bash setup-docker.sh
```

### Option 2: Native Mode (Linux/macOS/Windows)

```bash
# Install dependencies
pip install -r requirements.txt

# Run collector
bash run-local.sh
```

## 📁 Project Structure

```
enphase_monitoring/
├── README.md                 # This file
├── .gitignore              # Git ignore rules
├── .env                    # Configuration file
├── requirements.txt         # Python dependencies
│
├── docker/                 # Docker configuration
│   ├── docker-compose.yml    # Docker orchestration
│   ├── Dockerfile            # Container image
│   └── entrypoint.sh         # Container entrypoint
├── setup-docker.sh          # Docker setup script
├── run-local.sh             # Native mode runner
│
├── src/                     # Source code
│   ├── enphase_collector.py  # Main collector daemon
│   ├── enphase_token.py      # Auth & mDNS discovery
│   └── energy_advisor.py     # AI recommendations
│
├── docs/                   # Documentation
│   ├── AUTHENTICATION.md
│   ├── SYSTEM.md
│   └── QUICKSTART.md
│
├── examples/               # Example scripts
│   └── discover_gateways.py
│
├── tests/                  # Test scripts
│   ├── test_auth.sh
│   ├── test_env.py
│   └── test_login.py
│
├── dashboards/            # Grafana dashboards
├── config/                # Configuration files
└── data/                  # Persistent data (gitignored)
```

## ⚙️ Configuration

Edit `.env` file to customize:

```bash
# Gateway Configuration (optional - auto-discovery works if mDNS is set up)
ENPHASE_GATEWAY_IP=192.168.50.42
ENPHASE_GATEWAY_SERIAL=122140070291
ENPHASE_GATEWAY_PORT=443

# Polling Configuration (default: 300 seconds = 5 minutes)
ENPHASE_POLL_INTERVAL_SECONDS=300

# Authentication (optional - for auto token refresh)
ENLIGHTEN_EMAIL=your-email@example.com
ENLIGHTEN_PASSWORD=your-password

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token-here
```

## 🔧 Troubleshooting

### mDNS Discovery Not Working

**Linux:**
```bash
# Install libnss-mdns
sudo apt-get install libnss-mdns

# Configure NSS
sudo nano /etc/nsswitch.conf
# Add: hosts: files mdns4_minimal [NOTFOUND=return] dns
```

**macOS/Windows:** Built-in support - no setup needed!

### Gateway Offline

If the gateway disappears, reduce polling frequency:
```bash
# In .env
ENPHASE_POLL_INTERVAL_SECONDS=600  # 10 minutes
```

### Container Restart Loop

Check logs:
```bash
docker logs enphase_collector --tail 50
```

## 📊 Access Points

After starting the system:

- **Grafana**: http://localhost:3000 (admin/admin)
- **InfluxDB**: http://localhost:8086
- **Collector logs**: `docker logs -f enphase_collector`

## 🧪 Testing

```bash
# Test authentication
bash tests/test_auth.sh

# Test environment
python tests/test_env.py

# Test login
python tests/test_login.py

# Discover gateways
python examples/discover_gateways.py
```

## 📚 Documentation

- [SYSTEM.md](docs/SYSTEM.md) - Architecture overview
- [AUTHENTICATION.md](docs/AUTHENTICATION.md) - Token management
- [QUICKSTART.md](docs/QUICKSTART.md) - Detailed setup guide
- [DOCKER_NETWORK_TROUBLESHOOTING.md](docs/DOCKER_NETWORK_TROUBLESHOOTING.md) - Network issues

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

[Your License Here]

## 🙏 Acknowledgments

- Enphase Energy for the gateway API
- InfluxDB for time-series database
- Grafana for visualization
- Avahi for mDNS support

---

**Note**: This system polls your Enphase gateway. Be respectful with polling intervals to avoid overloading the gateway. Default is 5 minutes, which provides good data granularity without stressing the gateway.
