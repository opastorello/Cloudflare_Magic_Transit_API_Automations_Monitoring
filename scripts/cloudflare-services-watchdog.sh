#!/bin/bash
#
# Cloudflare Services Watchdog
# Monitors all Cloudflare-related services and restarts them if needed
#
# Version: 1.2
# Date: 2026-01-20
#
# Services monitored:
#   - cloudflare-webhook (webhook receiver - notifications only)
#   - cloudflare-analytics-monitor (network analytics polling)
#   - cloudflare-autowithdraw (BGP withdraw manager - CRITICAL)
#   - cloudflare-dashboard (web dashboard)
#
# Note: cloudflare-mt-withdrawals cron is disabled since v2.1.0
#       All withdrawals are handled by cloudflare-autowithdraw service
#

LOG_FILE="/root/Cloudflare_MT_Integration/logs/watchdog.log"
TELEGRAM_BOT="YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT="YOUR_TELEGRAM_CHAT_ID"

# Services to monitor (systemd)
SERVICES=(
    "cloudflare-webhook"
    "cloudflare-analytics-monitor"
    "cloudflare-autowithdraw"
    "cloudflare-dashboard"
)

# Cron jobs to verify (file existence)
# Note: cloudflare-mt-withdrawals disabled since v2.1.0
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

#
# Check systemd services
#
for SERVICE in "${SERVICES[@]}"; do
    if ! systemctl is-active --quiet "$SERVICE"; then
        log "WARNING: $SERVICE is not running. Attempting restart..."
        ISSUES_FOUND=$((ISSUES_FOUND + 1))

        # Try to restart
        systemctl restart "$SERVICE"
        sleep 3

        # Check if restart was successful
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

#
# Check cron jobs exist
#
for CRON_FILE in "${CRON_JOBS[@]}"; do
    if [ ! -f "$CRON_FILE" ]; then
        log "ERROR: Cron job missing: $CRON_FILE"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
        ISSUES_FAILED=$((ISSUES_FAILED + 1))
        CRON_NAME=$(basename "$CRON_FILE")
        DETAILS="${DETAILS}❌ \`${CRON_NAME}\` - MISSING\n"
    fi
done

#
# Send notification if any issues were found
#
if [ $ISSUES_FOUND -gt 0 ]; then
    if [ $ISSUES_FAILED -gt 0 ]; then
        # Critical alert - some services could not be recovered
        EMOJI="🚨🚨🚨"
        STATUS="CRITICAL - Manual intervention required"
        PRIORITY="HIGH"
    else
        # Warning - all services recovered
        EMOJI="⚠️"
        STATUS="All services recovered"
        PRIORITY="INFO"
    fi

    MESSAGE="🛡️ *CLOUDFLARE DDoS PROTECTION*

${EMOJI} *WATCHDOG ALERT*

🖥️ *Server:* \`$(hostname -f)\`
⏱️ *Time:* \`$(date -u '+%Y-%m-%d %H:%M:%S UTC')\`

📊 *SUMMARY*
• Issues found: ${ISSUES_FOUND}
• Fixed: ${ISSUES_FIXED}
• Failed: ${ISSUES_FAILED}

📋 *DETAILS*
${DETAILS}
🔔 *Status:* ${STATUS}

🏢 *GOLINE SOC* | _Services Watchdog_"

    send_telegram "$MESSAGE"
fi

#
# Rotate log file if > 1MB
#
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 1048576 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log "Log file rotated"
    fi
fi

exit 0
