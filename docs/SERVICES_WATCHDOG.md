# Cloudflare Services Watchdog

**Script**: `cloudflare-services-watchdog.sh`
**Version**: 1.2
**Last Updated**: 2026-01-22

---

## Overview

Bash script that monitors all Cloudflare-related systemd services and automatically restarts them if they fail. Runs via cron every 5 minutes.

### Services Monitored

| Service | Purpose | Criticality |
|---------|---------|-------------|
| `cloudflare-webhook` | Webhook receiver (notifications) | HIGH |
| `cloudflare-analytics-monitor` | GraphQL poller (notifications) | MEDIUM |
| `cloudflare-autowithdraw` | BGP withdraw manager | **CRITICAL** |
| `cloudflare-dashboard` | Web dashboard | MEDIUM |

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WATCHDOG FLOW (Every 5 minutes)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. For each service in SERVICES list:                                       │
│     └─► systemctl is-active --quiet $SERVICE                                │
│                                                                              │
│  2. If service is DOWN:                                                      │
│     ├─► Log warning                                                          │
│     ├─► systemctl restart $SERVICE                                          │
│     ├─► Wait 3 seconds                                                       │
│     └─► Check if restart succeeded                                          │
│                                                                              │
│  3. For each cron job in CRON_JOBS list:                                    │
│     └─► Check if file exists                                                │
│                                                                              │
│  4. If any issues found:                                                     │
│     └─► Send Telegram notification with summary                             │
│                                                                              │
│  5. Rotate log file if > 1MB                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Script Location

```
/root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh
```

### Services Array

```bash
SERVICES=(
    "cloudflare-webhook"
    "cloudflare-analytics-monitor"
    "cloudflare-autowithdraw"
    "cloudflare-dashboard"
)
```

### Cron Jobs Verified

```bash
CRON_JOBS=(
    "/etc/cron.d/cloudflare-services-watchdog"
)
```

**Note**: `cloudflare-mt-withdrawals` was removed in v1.1 (disabled since v2.1.0 of the project).

### Log File

```
/root/Cloudflare_MT_Integration/logs/watchdog.log
```

Auto-rotated when exceeds 1MB.

---

## Cron Configuration

### File: `/etc/cron.d/cloudflare-services-watchdog`

```cron
# Cloudflare Services Watchdog
# Monitors and auto-restarts Cloudflare services
# Runs every 5 minutes

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/5 * * * * root /root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh
```

### Verify Cron is Active

```bash
# Check cron file exists
ls -la /etc/cron.d/cloudflare-services-watchdog

# Check cron syntax
cat /etc/cron.d/cloudflare-services-watchdog

# Check recent executions in syslog
grep -i cron /var/log/syslog | grep watchdog | tail -5
```

---

## Telegram Notifications

### Alert Format

When issues are detected, a Telegram notification is sent:

```
🛡️ *CLOUDFLARE DDoS PROTECTION*

⚠️ *WATCHDOG ALERT*

🖥️ *Server:* `lg.goline.ch`
⏱️ *Time:* `2026-01-19 14:30:00 UTC`

📊 *SUMMARY*
• Issues found: 1
• Fixed: 1
• Failed: 0

📋 *DETAILS*
✅ `cloudflare-autowithdraw` - restarted

🔔 *Status:* All services recovered

🏢 *GOLINE SOC* | _Services Watchdog_
```

### Alert Levels

| Condition | Emoji | Priority |
|-----------|-------|----------|
| All services recovered | ⚠️ | INFO |
| Some services failed to restart | 🚨🚨🚨 | CRITICAL |

---

## Manual Execution

### Run Watchdog Manually

```bash
# Execute watchdog
/root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh

# With verbose output (check log after)
/root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh && tail -20 /root/Cloudflare_MT_Integration/logs/watchdog.log
```

### Check Log

```bash
# Recent entries
tail -50 /root/Cloudflare_MT_Integration/logs/watchdog.log

# Watch live
tail -f /root/Cloudflare_MT_Integration/logs/watchdog.log

# Search for errors
grep -i "error\|failed" /root/Cloudflare_MT_Integration/logs/watchdog.log
```

---

## Script Source

```bash
#!/bin/bash
#
# Cloudflare Services Watchdog
# Monitors all Cloudflare-related services and restarts them if needed
#
# Version: 1.1
# Date: 2026-01-19
#
# Services monitored:
#   - cloudflare-webhook (webhook receiver - notifications only)
#   - cloudflare-analytics-monitor (network analytics polling)
#   - cloudflare-autowithdraw (BGP withdraw manager - CRITICAL)
#
# Note: cloudflare-mt-withdrawals cron is disabled since v2.1.0
#       All withdrawals are handled by cloudflare-autowithdraw service

LOG_FILE="/root/Cloudflare_MT_Integration/logs/watchdog.log"
TELEGRAM_BOT="<bot_token>"
TELEGRAM_CHAT="<chat_id>"

# Services to monitor (systemd)
SERVICES=(
    "cloudflare-webhook"
    "cloudflare-analytics-monitor"
    "cloudflare-autowithdraw"
    "cloudflare-dashboard"
)

# Cron jobs to verify (file existence)
CRON_JOBS=(
    "/etc/cron.d/cloudflare-services-watchdog"
)

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT}" \
        -d "parse_mode=Markdown" \
        -d "text=${message}" > /dev/null 2>&1
}

# Track issues for summary notification
ISSUES_FOUND=0
ISSUES_FIXED=0
ISSUES_FAILED=0
DETAILS=""

# Check systemd services
for SERVICE in "${SERVICES[@]}"; do
    if ! systemctl is-active --quiet "$SERVICE"; then
        log "WARNING: $SERVICE is not running. Attempting restart..."
        ISSUES_FOUND=$((ISSUES_FOUND + 1))

        systemctl restart "$SERVICE"
        sleep 3

        if systemctl is-active --quiet "$SERVICE"; then
            log "SUCCESS: $SERVICE restarted successfully"
            ISSUES_FIXED=$((ISSUES_FIXED + 1))
            DETAILS="${DETAILS}✅ \`${SERVICE}\` - restarted\n"
        else
            log "ERROR: Failed to restart $SERVICE"
            ISSUES_FAILED=$((ISSUES_FAILED + 1))
            DETAILS="${DETAILS}❌ \`${SERVICE}\` - RESTART FAILED\n"
        fi
    fi
done

# Check cron jobs exist
for CRON_FILE in "${CRON_JOBS[@]}"; do
    if [ ! -f "$CRON_FILE" ]; then
        log "ERROR: Cron job missing: $CRON_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
        ISSUES_FAILED=$((ISSUES_FAILED + 1))
        CRON_NAME=$(basename "$CRON_FILE")
        DETAILS="${DETAILS}❌ \`${CRON_NAME}\` - MISSING\n"
    fi
done

# Send notification if any issues were found
if [ $ISSUES_FOUND -gt 0 ]; then
    # ... notification logic ...
fi

# Rotate log file if > 1MB
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 1048576 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log "Log file rotated"
    fi
fi

exit 0
```

---

## Troubleshooting

### Watchdog Not Running

```bash
# Check cron daemon
systemctl status cron

# Check cron file permissions
ls -la /etc/cron.d/cloudflare-services-watchdog
# Should be: -rw-r--r-- root root

# Check script permissions
ls -la /root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh
# Should be executable: -rwxr-xr-x
chmod +x /root/Cloudflare_MT_Integration/scripts/cloudflare-services-watchdog.sh
```

### No Telegram Notifications

```bash
# Test Telegram manually
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT}" \
  -d "text=Test message from watchdog"

# Check for curl errors in log
grep -i "telegram\|curl" /root/Cloudflare_MT_Integration/logs/watchdog.log
```

### Service Won't Restart

```bash
# Check service status
systemctl status cloudflare-autowithdraw

# Check journal for errors
journalctl -u cloudflare-autowithdraw -n 50

# Try manual restart
systemctl restart cloudflare-autowithdraw
```

---

## Changelog

### v1.2 (2026-01-20)
- Added `cloudflare-dashboard` to services list (all 4 services now monitored)

### v1.1 (2026-01-19)
- Added `cloudflare-autowithdraw` to services list
- Removed `cloudflare-mt-withdrawals` from cron checks (deprecated)
- Updated documentation

### v1.0 (2026-01-19)
- Initial release
- Monitors webhook and analytics-monitor services
- Telegram notifications on issues

---

*GOLINE SOC - Cloudflare Magic Transit Integration*
