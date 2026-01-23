# Cloudflare Magic Transit Integration - Requirements

**Last Updated**: 2026-01-19
**Version**: 2.0.0

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Python Requirements](#2-python-requirements)
3. [System Services](#3-system-services)
4. [Network Requirements](#4-network-requirements)
5. [Cloudflare Requirements](#5-cloudflare-requirements)
6. [Installation Guide](#6-installation-guide)
7. [Verification](#7-verification)

---

## 1. System Requirements

### Operating System

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| **Alternative** | Debian 11 | Debian 12 |
| **Architecture** | x86_64 | x86_64 |

### Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 1 core | 2+ cores |
| **RAM** | 512 MB | 1 GB |
| **Disk** | 1 GB free | 5 GB free |
| **Network** | 10 Mbps | 100 Mbps |

### Software Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| **Python** | 3.10+ | Script runtime |
| **SQLite** | 3.x | Database |
| **Apache** | 2.4+ | HTTPS reverse proxy |
| **curl** | any | Telegram notifications |
| **systemd** | any | Service management |
| **cron** | any | Scheduled tasks |

---

## 2. Python Requirements

### Python Version

```bash
# Check Python version
python3 --version
# Required: Python 3.10 or higher
```

### Standard Library (Built-in)

These modules are included with Python - no installation needed:

| Module | Purpose |
|--------|---------|
| `json` | JSON parsing |
| `sqlite3` | SQLite database |
| `logging` | Logging |
| `datetime` | Date/time handling |
| `hashlib` | Hash generation |
| `hmac` | HMAC verification |
| `ipaddress` | IP address handling |
| `argparse` | CLI argument parsing |
| `signal` | Signal handling |
| `os`, `sys` | System operations |
| `time` | Time operations |
| `random`, `string` | ID generation |
| `pathlib` | Path operations |
| `typing` | Type hints |

### External Packages (pip)

| Package | Version | Purpose | Installation |
|---------|---------|---------|--------------|
| **Flask** | 2.0+ | Web framework (webhook receiver) | `pip3 install flask` |
| **requests** | 2.28+ | HTTP client (API calls) | `pip3 install requests` |

### Install Python Packages

```bash
# Install required packages
pip3 install flask requests

# Or using apt (Debian/Ubuntu)
apt install python3-flask python3-requests

# Verify installation
python3 -c "import flask; import requests; print('OK')"
```

### requirements.txt

Create `/root/Cloudflare_MT_Integration/requirements.txt`:

```
flask>=2.0.0
requests>=2.28.0
```

Install with:
```bash
pip3 install -r /root/Cloudflare_MT_Integration/requirements.txt
```

---

## 3. System Services

### Systemd Services

| Service | File | Purpose |
|---------|------|---------|
| `cloudflare-webhook` | `/etc/systemd/system/cloudflare-webhook.service` | Webhook receiver |
| `cloudflare-analytics-monitor` | `/etc/systemd/system/cloudflare-analytics-monitor.service` | Network Analytics poller |

#### cloudflare-webhook.service

```ini
[Unit]
Description=Cloudflare Magic Transit Webhook Receiver
Documentation=https://developers.cloudflare.com/notifications/
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/Cloudflare_MT_Integration
ExecStart=/usr/bin/python3 /root/Cloudflare_MT_Integration/scripts/cloudflare-webhook-receiver.py
Restart=always
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflare-webhook
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/root/Cloudflare_MT_Integration/logs /root/Cloudflare_MT_Integration/db

[Install]
WantedBy=multi-user.target
```

#### cloudflare-analytics-monitor.service

```ini
[Unit]
Description=Cloudflare Network Analytics Monitor
Documentation=https://developers.cloudflare.com/analytics/graphql-api/
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/Cloudflare_MT_Integration
ExecStart=/usr/bin/python3 /root/Cloudflare_MT_Integration/scripts/cloudflare-network-analytics-monitor.py
Restart=always
RestartSec=30
StartLimitIntervalSec=300
StartLimitBurst=5
WatchdogSec=600
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflare-analytics-monitor
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/root/Cloudflare_MT_Integration/logs /root/Cloudflare_MT_Integration/db

[Install]
WantedBy=multi-user.target
```

### Cron Jobs

| Cron | File | Schedule | Purpose |
|------|------|----------|---------|
| Withdrawals | `/etc/cron.d/cloudflare-mt-withdrawals` | */5 min | Process pending BGP withdrawals |
| Watchdog | `/etc/cron.d/cloudflare-services-watchdog` | */5 min | Monitor and restart services |

#### cloudflare-mt-withdrawals

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/5 * * * * root /usr/bin/python3 /root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py >> /root/Cloudflare_MT_Integration/logs/withdrawal_cron.log 2>&1
```

#### cloudflare-services-watchdog

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/5 * * * * root /root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh >/dev/null 2>&1
```

### Apache Configuration

Required modules:
```bash
a2enmod proxy proxy_http ssl headers
```

ProxyPass configuration (in SSL vhost):
```apache
ProxyPreserveHost On
ProxyPass /webhook http://127.0.0.1:8080/webhook
ProxyPassReverse /webhook http://127.0.0.1:8080/webhook
ProxyPass /mt-health http://127.0.0.1:8080/mt-health
ProxyPassReverse /mt-health http://127.0.0.1:8080/mt-health
```

---

## 4. Network Requirements

### Inbound Ports

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 443 | TCP | Cloudflare IPs | Webhook receiver (via Apache) |
| 8080 | TCP | localhost only | Flask internal port |

### Outbound Access

| Destination | Port | Protocol | Purpose |
|-------------|------|----------|---------|
| `api.cloudflare.com` | 443 | HTTPS | Cloudflare API |
| `api.telegram.org` | 443 | HTTPS | Telegram notifications |

### Cloudflare Webhook IPs

Cloudflare sends webhooks from these IP ranges. Ensure they can reach port 443:

```
173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22
```

### DNS Requirements

| Hostname | Resolution | Purpose |
|----------|------------|---------|
| `your-server.example.com` | Server IP | Webhook endpoint |
| `api.cloudflare.com` | Cloudflare | API access |
| `api.telegram.org` | Telegram | Notifications |

---

## 5. Cloudflare Requirements

### API Token Permissions

| Permission | Scope | Required For |
|------------|-------|--------------|
| `Account.Magic Transit Prefix` | Read + Write | BGP prefix management |
| `Account.Account Analytics` | Read | Network Analytics API |
| `Account.Account Settings` | Read | Account information |

### Webhook Configuration

1. **Cloudflare Dashboard** → **Notifications** → **Destinations**
2. Create **Webhook** destination:
   - **URL**: `https://your-server.example.com/webhook/cloudflare`
   - **Secret**: `YOUR_WEBHOOK_SECRET`

### Notification Policies

Create policies for these alert types:

| Alert Type | Priority |
|------------|----------|
| Advanced Layer 3/4 DDoS Attack Alert | HIGH |
| HTTP DDoS Attack Alert | HIGH |
| Magic Transit Tunnel Health Alert | HIGH |
| Magic Network Monitoring: DDoS Attack | HIGH |
| Magic Network Monitoring: Volumetric Attack | MEDIUM |
| BGP Hijack Event Notification | CRITICAL |
| Health Check Status Notification | MEDIUM |
| Cloudflare Status Alert | INFO |

### BGP Prefixes

Ensure these prefixes are configured in Cloudflare Magic Transit:

| Prefix | Type |
|--------|------|
| `198.51.100.0/24` | IPv4 |
| `192.0.2.0/24` | IPv4 |
| `203.0.113.0/24` | IPv4 |
| `203.0.113.128/25` | IPv4 |
| `2001:db8::/32` | IPv6 |

---

## 6. Installation Guide

### Quick Install

```bash
# 1. Install system packages
apt update
apt install python3 python3-pip python3-flask python3-requests apache2 sqlite3 curl

# 2. Enable Apache modules
a2enmod proxy proxy_http ssl headers
systemctl restart apache2

# 3. Create directories
mkdir -p /root/Cloudflare_MT_Integration/{config,db,logs/webhooks,scripts,docs,backup}

# 4. Copy scripts and config files
# (Copy all files from repository)

# 5. Set permissions
chmod +x /root/Cloudflare_MT_Integration/scripts/*.py
chmod +x /root/Cloudflare_MT_Integration/scripts/*.sh

# 6. Create symlink
ln -sf /root/Cloudflare_MT_Integration/scripts/cloudflare-prefix-manager.py /usr/local/bin/cloudflare-prefix-manager

# 7. Install systemd services
cp cloudflare-webhook.service /etc/systemd/system/
cp cloudflare-analytics-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cloudflare-webhook cloudflare-analytics-monitor

# 8. Install cron jobs
cp cloudflare-mt-withdrawals /etc/cron.d/
cp cloudflare-services-watchdog /etc/cron.d/

# 9. Configure Apache (add ProxyPass to SSL vhost)
# Edit /etc/apache2/sites-available/your-ssl-site.conf

# 10. Start services
systemctl start cloudflare-webhook cloudflare-analytics-monitor
```

### Configuration

1. Edit `/root/Cloudflare_MT_Integration/config/settings.json`:
   - Add Cloudflare API token
   - Add Telegram bot token and chat ID
   - Set webhook secret

2. Edit `/root/Cloudflare_MT_Integration/config/prefix_mapping.json`:
   - Add BGP prefix IDs from Cloudflare

---

## 7. Verification

### Check Python Dependencies

```bash
python3 -c "
import flask
import requests
import sqlite3
import json
import logging
print('All Python dependencies OK')
"
```

### Check Services

```bash
# Service status
systemctl status cloudflare-webhook cloudflare-analytics-monitor

# Cron jobs
ls -la /etc/cron.d/cloudflare-*

# Symlink
ls -la /usr/local/bin/cloudflare-prefix-manager
```

### Check Connectivity

```bash
# Health check endpoint
curl -s https://your-server.example.com/mt-health | jq

# Cloudflare API
curl -s -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.cloudflare.com/client/v4/user/tokens/verify

# Telegram
curl -s "https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN/getMe"
```

### Test System

```bash
# Full system test
python3 /root/Cloudflare_MT_Integration/scripts/test_system.py

# API connection test
python3 /root/Cloudflare_MT_Integration/scripts/test_connection.py

# Prefix status
cloudflare-prefix-manager status
```

### Check Logs

```bash
# Webhook receiver
journalctl -u cloudflare-webhook -f

# Analytics monitor
journalctl -u cloudflare-analytics-monitor -f

# Watchdog
tail -f /root/Cloudflare_MT_Integration/logs/watchdog.log
```

---

## Summary

| Component | Requirement |
|-----------|-------------|
| **OS** | Ubuntu 22.04+ / Debian 11+ |
| **Python** | 3.10+ |
| **Packages** | flask, requests |
| **Services** | systemd, cron, apache2 |
| **Network** | HTTPS inbound (443), outbound to Cloudflare/Telegram |
| **Cloudflare** | API token with Magic Transit permissions |
| **Telegram** | Bot token + chat ID |

---

*Generated: 2026-01-19 - GOLINE SOC*

