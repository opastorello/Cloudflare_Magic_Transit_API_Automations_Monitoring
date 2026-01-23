# Magic Transit Database System

Persistent storage for attack events, withdrawal history, webhook events, and network analytics events.

**Database**: `/root/Cloudflare_MT_Integration/db/magic_transit.db`
**Type**: SQLite 3
**Version**: 2.3.0
**Last Updated**: 2026-01-21

---

## Table of Contents

- [Overview](#overview)
- [Architecture (v2.1.0)](#architecture-v210)
- [Database Schema](#database-schema)
- [Webhook Events](#webhook-events)
- [Scripts](#scripts)
- [Usage Examples](#usage-examples)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Overview

The database system provides:

- **Attack event logging** for all START/END/WITHDRAW events
- **Withdrawal history** for auditing and statistics
- **Webhook event storage** for all received Cloudflare webhooks
- **Network analytics events** from GraphQL polling
- **Attack correlation** via alert_id (links START → END → WITHDRAW events)

> **Note v2.1.0**: The `pending_withdrawals` table is **deprecated**. All withdrawals are now
> handled by `cloudflare-autowithdraw.service` which logs directly to `attack_events` and
> `withdrawal_history`.

### Why SQLite?

- Zero configuration (file-based)
- Built into Python (no external dependencies)
- ACID compliant
- Easy backup (single file)
- Perfect for low-volume, high-reliability use case

---

## Architecture (v2.1.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WEBHOOK RECEIVER                              │
│                   (cloudflare-webhook-receiver.py)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ATTACK START Event                                                  │
│       │                                                              │
│       └──► log_attack_event('START', payload) ─────► attack_events   │
│                                                                      │
│  ATTACK END Event                                                    │
│       │                                                              │
│       └──► log_attack_event('END', payload) ────────► attack_events  │
│            (NO withdraw - delegated to autowithdraw)                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        AUTOWITHDRAW DAEMON                           │
│                    (cloudflare-autowithdraw.py)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Prefix calm for 15 minutes                                          │
│       │                                                              │
│       ├──► Withdraw via Cloudflare API                               │
│       │                                                              │
│       ├──► log_withdraw_to_db() ───┬────────────► attack_events      │
│       │                            │              (event_type=WITHDRAW)
│       │                            │                                 │
│       │                            └────────────► withdrawal_history │
│       │                                                              │
│       └──► Send Telegram notification                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   NETWORK ANALYTICS MONITOR                          │
│              (cloudflare-network-analytics-monitor.py)               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GraphQL poll (every 5 min)                                          │
│       │                                                              │
│       └──► save_event() ─────────────► network_analytics_events      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
│         │           │      (table)      │                            │
│         │           └──────────────────┘                             │
│         │                   │                                        │
│         │                   │ (cron */5 min)                         │
│         │                   ▼                                        │
│         │    ┌────────────────────────────┐                          │
│         │    │ cloudflare-check-pending-withdrawals.py │                        │
│         │    └────────────────────────────┘                          │
│         │                   │                                        │
│         │                   ▼                                        │
│         │         get_pending_withdrawals()                          │
│         │         WHERE withdraw_after <= NOW()                      │
│         │                   │                                        │
│         │                   ▼                                        │
│         │            Withdraw via API                                │
│         │                   │                                        │
│         └───────────┬───────┘                                        │
│                     ▼                                                │
│              mark_withdrawn()                                        │
│                     │                                                │
│                     ▼                                                │
│            ┌──────────────────┐                                      │
│            │ withdrawal_history │                                    │
│            │      (table)      │                                     │
│            └──────────────────┘                                      │
│                     │                                                │
│                     ▼                                                │
│            Telegram Notification                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Table: `pending_withdrawals`

Stores BGP prefix withdrawals waiting for the 15-minute constraint.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `prefix` | TEXT | BGP prefix CIDR (e.g., "185.54.82.0/24") |
| `attack_id` | TEXT | Cloudflare attack ID |
| `policy_id` | TEXT | Cloudflare policy ID |
| `policy_name` | TEXT | Policy name |
| `target_ip` | TEXT | Target IP address |
| `attack_type` | TEXT | Alert type (e.g., "advanced_ddos_attack_l4_alert") |
| `advertised_at` | DATETIME | When prefix was advertised |
| `withdraw_after` | DATETIME | Earliest withdrawal time (advertised_at + 15min) |
| `attack_ended_at` | DATETIME | When attack END event was received |
| `created_at` | DATETIME | Record creation time |
| `status` | TEXT | "pending", "withdrawn", "failed" |
| `retry_count` | INTEGER | Number of failed attempts |
| `last_error` | TEXT | Last error message (if failed) |

**Unique Constraint**: `(prefix, attack_id)` - Prevents duplicate entries for same attack.

### Table: `withdrawal_history`

Permanent record of all completed withdrawals.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `prefix` | TEXT | BGP prefix CIDR |
| `attack_id` | TEXT | Cloudflare attack ID |
| `policy_id` | TEXT | Cloudflare policy ID |
| `policy_name` | TEXT | Policy name |
| `target_ip` | TEXT | Target IP address |
| `attack_type` | TEXT | Alert type |
| `advertised_at` | DATETIME | When prefix was advertised |
| `attack_ended_at` | DATETIME | When attack ended |
| `withdrawn_at` | DATETIME | When prefix was withdrawn |
| `attack_duration_seconds` | INTEGER | Time from advertise to attack end |
| `protection_duration_seconds` | INTEGER | Time from advertise to withdraw |
| `withdraw_method` | TEXT | "immediate", "auto_scheduled", "manual" |
| `status` | TEXT | "success", "failed" |
| `notes` | TEXT | Additional notes or error messages |
| `created_at` | DATETIME | Record creation time |

### Table: `attack_events`

Log of all attack events (START, END, ADVERTISE, WITHDRAW).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `event_type` | TEXT | "START", "END", "ADVERTISE", "WITHDRAW" |
| `alert_type` | TEXT | Cloudflare alert type |
| `attack_id` | TEXT | Cloudflare attack ID |
| `policy_id` | TEXT | Cloudflare policy ID |
| `policy_name` | TEXT | Policy name |
| `prefix` | TEXT | Identified BGP prefix |
| `target_ip` | TEXT | Target IP address |
| `target_port` | INTEGER | Target port |
| `protocol` | TEXT | Protocol (TCP/UDP) |
| `attack_vector` | TEXT | Attack vector description |
| `packets_per_second` | TEXT | PPS at event time |
| `megabits_per_second` | TEXT | Mbps at event time |
| `severity` | TEXT | Alert severity |
| `action_taken` | TEXT | Action taken by system |
| `raw_payload` | TEXT | Full JSON payload (for debugging) |
| `created_at` | DATETIME | Event timestamp |

**event_type Values:**
| Value | Description | Source |
|-------|-------------|--------|
| `START` | Attack detected | Webhook receiver |
| `END` | Attack ended | Webhook receiver |
| `ADVERTISE` | Prefix announced via BGP | Dashboard/Auto-advertise |
| `WITHDRAW` | Prefix withdrawn from BGP | Dashboard/Autowithdraw |

**action_taken Values (v2.3.0):**
| Value | Description | Used By |
|-------|-------------|---------|
| `mitigating` | Cloudflare actively mitigating attack | DDoS L4 attacks |
| `auto_advertised` | Cloudflare auto-announced prefix | fbm_auto_advertisement |
| `notified` | Alert sent, no auto-mitigation | MNM alerts |
| `notified_autowithdraw_handles` | Attack ended, withdraw delegated | Attack END |
| `withdrawn_auto` | Prefix withdrawn by autowithdraw | Autowithdraw daemon |
| `withdrawn_manual` | Prefix withdrawn manually | Dashboard |
| `withdrawn_immediate` | Prefix withdrawn immediately | Emergency |
| `advertised_manual` | Prefix announced manually | Dashboard |
| `processing` | Event being processed | Various |

### Table: `webhook_events`

Stores ALL received webhooks for correlation and analysis.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `received_at` | DATETIME | When webhook was received |
| `alert_type` | TEXT | Cloudflare alert type |
| `event_state` | TEXT | "ALERT_STATE_EVENT_START", "ALERT_STATE_EVENT_END", etc. |
| `alert_id` | TEXT | Attack/incident ID for correlation |
| `policy_id` | TEXT | Cloudflare policy ID |
| `policy_name` | TEXT | Policy name |
| `target_ip` | TEXT | Target IP address |
| `target_prefix` | TEXT | Identified BGP prefix |
| `source_ip` | TEXT | Webhook sender IP |
| `processed` | INTEGER | 1 = processed, 0 = pending |
| `action_taken` | TEXT | "received", "imported", etc. |
| `payload` | JSON | Full raw webhook payload |

**Unique Constraint**: `(alert_id, event_state)` - Prevents duplicate webhooks.

### Table: `network_analytics_events`

Stores events from the Network Analytics Monitor (GraphQL API polling).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `event_hash` | TEXT | SHA256 hash for deduplication (UNIQUE) |
| `attack_id` | TEXT | Cloudflare attack ID |
| `event_datetime` | DATETIME | Event timestamp from Cloudflare |
| `attack_vector` | TEXT | Attack type (SYN Flood, UDP Flood, etc.) |
| `rule_name` | TEXT | DDoS rule name |
| `rule_id` | TEXT | DDoS rule ID |
| `source_ip` | TEXT | Source IP address |
| `source_port` | INTEGER | Source port |
| `source_asn` | INTEGER | Source ASN number (v2.8.6) |
| `source_asn_name` | TEXT | Source ASN organization name (v2.8.6) |
| `source_country` | TEXT | Source country ISO code (v2.8.6) |
| `destination_ip` | TEXT | Destination IP address |
| `destination_port` | INTEGER | Destination port |
| `protocol` | TEXT | Protocol (TCP/UDP) |
| `tcp_flags` | TEXT | TCP flags (SYN, ACK, etc.) |
| `colo_code` | TEXT | Data center code (AMS, SOF, etc.) |
| `colo_country` | TEXT | Data center country |
| `packets` | INTEGER | Number of packets dropped |
| `bits` | INTEGER | Bits dropped |
| `outcome` | TEXT | Traffic outcome (drop) |
| `mitigation_reason` | TEXT | Mitigation action taken |
| `notified_at` | DATETIME | When Telegram notification was sent |
| `raw_data` | JSON | Full event payload |

**Deduplication**: SHA256 hash of `(datetime + attackId + sourceIP + destIP + destPort)`

**Note**: This table is populated by the Network Analytics Monitor (`cloudflare-network-analytics-monitor.py`), which polls the GraphQL API every 5 minutes with a 15-minute lookback window.

### Table: `prefix_calm_status`

Tracks the calm status of BGP prefixes for dashboard integration. Updated every check cycle (60 seconds) by the autowithdraw daemon.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `prefix` | TEXT | CIDR notation (UNIQUE) |
| `advertised` | BOOLEAN | `1` if advertised, `0` if withdrawn |
| `under_attack` | BOOLEAN | `1` if under attack, `0` if calm |
| `calm_since` | DATETIME | When the prefix became calm (UTC) |
| `last_attack_packets` | INTEGER | Dropped packets during last attack |
| `last_attack_mbps` | REAL | Dropped traffic (Mbps) during last attack |
| `mitigation_systems` | TEXT | Comma-separated list of mitigation systems |
| `updated_at` | DATETIME | Last update timestamp (UTC) |

**Purpose**: Shares autowithdraw daemon state with web dashboard for real-time calm time display.

**Updated by**: `cloudflare-autowithdraw.py` (`update_prefix_calm_status()`)

**Read by**: `dashboard/app.py` (`get_prefix_calm_status()`)

### Indexes

```sql
CREATE INDEX idx_pending_status ON pending_withdrawals(status);
CREATE INDEX idx_pending_withdraw_after ON pending_withdrawals(withdraw_after);
CREATE INDEX idx_history_prefix ON withdrawal_history(prefix);
CREATE INDEX idx_events_attack_id ON attack_events(attack_id);
CREATE INDEX idx_webhook_alert_type ON webhook_events(alert_type);
CREATE INDEX idx_webhook_received_at ON webhook_events(received_at);
CREATE INDEX idx_webhook_target_ip ON webhook_events(target_ip);
CREATE INDEX idx_network_analytics_hash ON network_analytics_events(event_hash);
CREATE INDEX idx_network_analytics_datetime ON network_analytics_events(event_datetime);
CREATE INDEX idx_network_analytics_attack_id ON network_analytics_events(attack_id);
CREATE INDEX idx_calm_prefix ON prefix_calm_status(prefix);
```

---

## Webhook Events

The `webhook_events` table provides:

- **Complete history** of all Cloudflare webhooks received
- **Attack correlation** - link START and END events via `alert_id`
- **Statistics** - count by type, time period, target
- **Debugging** - full payload stored as JSON

### Querying Webhooks

```bash
# Recent webhooks
python3 /root/Cloudflare_MT_Integration/scripts/import_webhooks.py --recent 10

# Statistics
python3 /root/Cloudflare_MT_Integration/scripts/import_webhooks.py --stats

# Correlate START/END for an attack
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT received_at, event_state, action_taken
   FROM webhook_events
   WHERE alert_id = 'attack-id-here'
   ORDER BY received_at"
```

### Attack Correlation

When both START and END webhooks are received for the same attack:

```
Attack ID: cf-attack-12345
├── 2026-01-19 00:15:00 | ALERT_STATE_EVENT_START | received
└── 2026-01-19 00:45:00 | ALERT_STATE_EVENT_END   | received
```

Query completed attacks:

```sql
SELECT COUNT(DISTINCT w1.alert_id)
FROM webhook_events w1
WHERE w1.event_state = 'ALERT_STATE_EVENT_START'
AND EXISTS (
    SELECT 1 FROM webhook_events w2
    WHERE w2.alert_id = w1.alert_id
    AND w2.event_state = 'ALERT_STATE_EVENT_END'
);
```

### Import Existing Webhooks

```bash
# Import all JSON files from logs/webhooks/
python3 /root/Cloudflare_MT_Integration/scripts/import_webhooks.py

# Preview without importing
python3 /root/Cloudflare_MT_Integration/scripts/import_webhooks.py --dry-run

# Import single file
python3 /root/Cloudflare_MT_Integration/scripts/import_webhooks.py --file webhook_20260119.json
```

---

## Scripts

### db_manager.py

Database management module used by all other scripts.

**Location**: `/root/Cloudflare_MT_Integration/scripts/db_manager.py`

**Functions**:

| Function | Description |
|----------|-------------|
| `init_database()` | Create tables and indexes if not exist |
| `get_connection()` | Get SQLite connection with row factory |
| `add_pending_withdrawal(...)` | Add new pending withdrawal |
| `get_pending_withdrawals()` | Get withdrawals ready to process |
| `get_all_pending()` | Get all pending (regardless of time) |
| `mark_withdrawn(id, success, error, method)` | Complete a withdrawal |
| `log_attack_event(type, payload, prefix, action)` | Log attack event |
| `get_attack_history(limit)` | Get withdrawal history |
| `get_attack_events(limit)` | Get attack events |
| `get_stats()` | Get database statistics |
| `log_webhook_event(payload, source_ip, action, prefix)` | Log webhook event |
| `get_webhook_events(limit, alert_type, days)` | Get webhook events with filters |
| `get_webhook_by_alert_id(alert_id)` | Get all events for an attack (correlation) |
| `get_webhook_stats()` | Get webhook-specific statistics |
| `import_webhook_from_json(filepath)` | Import webhook from JSON file |

**Usage in Python**:

```python
from db_manager import (
    init_database, add_pending_withdrawal,
    get_pending_withdrawals, mark_withdrawn,
    log_attack_event, get_stats
)

# Initialize (called automatically on import)
init_database()

# Log attack event
log_attack_event('START', payload, prefix='185.54.82.0/24', action_taken='notified')

# Add pending withdrawal
record_id = add_pending_withdrawal(
    prefix='185.54.82.0/24',
    withdraw_after='2026-01-19 01:00:00',
    attack_id='cf-attack-123',
    policy_id='policy-456',
    target_ip='185.54.82.10'
)

# Get ready withdrawals
pending = get_pending_withdrawals()  # WHERE withdraw_after <= NOW()

# Mark as withdrawn
mark_withdrawn(record_id, success=True, method='auto_scheduled')

# Get stats
stats = get_stats()
print(f"Pending: {stats['pending_withdrawals']}")
```

### cloudflare-check-pending-withdrawals.py

Cron script that processes pending withdrawals.

**Location**: `/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py`

**Commands**:

```bash
# Process pending withdrawals (default - used by cron)
./cloudflare-check-pending-withdrawals.py

# Show current status
./cloudflare-check-pending-withdrawals.py --status

# Show withdrawal history
./cloudflare-check-pending-withdrawals.py --history
./cloudflare-check-pending-withdrawals.py --history --limit 50
```

**Output Example (--status)**:

```
======================================================================
PENDING WITHDRAWALS STATUS
======================================================================

Prefix               Attack ID       Withdraw After         Status
----------------------------------------------------------------------
185.54.82.0/24       test-2026011    2026-01-19 00:06:25    in 14m 43s
185.54.83.0/24       cf-atk-789      2026-01-19 00:15:00    in 23m 17s

----------------------------------------------------------------------
Pending: 2 | Total Withdrawals: 5 | Success: 5 | Events Today: 12
======================================================================
```

**Output Example (--history)**:

```
================================================================================
WITHDRAWAL HISTORY
================================================================================

Withdrawn At           Prefix               Method       Duration     Status
--------------------------------------------------------------------------------
2026-01-19 00:45:30    185.54.82.0/24       auto_schedu  18m 45s      ✅ success
2026-01-19 00:30:15    185.54.80.0/24       immediate    0m 5s        ✅ success
2026-01-18 23:15:00    185.54.82.0/24       auto_schedu  16m 30s      ✅ success
================================================================================
```

---

## Cron Job

**File**: `/etc/cron.d/cloudflare-mt-withdrawals`

```cron
# Cloudflare Magic Transit - Pending Withdrawals Checker
# Runs every 5 minutes to process scheduled BGP prefix withdrawals

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/5 * * * * root /usr/bin/python3 /root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py >> /root/Cloudflare_MT_Integration/logs/withdrawal_cron.log 2>&1
```

**Schedule**: Every 5 minutes (`*/5 * * * *`)

**Log Files**:
- `/root/Cloudflare_MT_Integration/logs/withdrawal_checker.log` - Script logs
- `/root/Cloudflare_MT_Integration/logs/withdrawal_cron.log` - Cron output

---

## Usage Examples

### Query Database Directly

```bash
# Open SQLite shell
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db

# View pending withdrawals
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT prefix, withdraw_after, status FROM pending_withdrawals WHERE status='pending'"

# View recent attack events
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT event_type, prefix, action_taken, created_at FROM attack_events ORDER BY id DESC LIMIT 10"

# View withdrawal history
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT prefix, withdrawn_at, withdraw_method, status FROM withdrawal_history ORDER BY id DESC LIMIT 10"

# Count events today
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT COUNT(*) FROM attack_events WHERE date(created_at) = date('now')"

# Get statistics
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT
    (SELECT COUNT(*) FROM pending_withdrawals WHERE status='pending') as pending,
    (SELECT COUNT(*) FROM withdrawal_history) as total_withdrawals,
    (SELECT COUNT(*) FROM attack_events) as total_events"
```

### Using the Checker Script

```bash
# Check current status (human-readable)
/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py --status

# View history
/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py --history

# Manually process pending (same as cron does)
/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py

# Check logs
tail -f /root/Cloudflare_MT_Integration/logs/withdrawal_checker.log
```

### Manual Database Operations

```bash
# Manually add a pending withdrawal (for testing)
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "INSERT INTO pending_withdrawals (prefix, withdraw_after, status)
   VALUES ('185.54.82.0/24', datetime('now', '+1 minute'), 'pending')"

# Manually remove a pending withdrawal
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "DELETE FROM pending_withdrawals WHERE prefix='185.54.82.0/24'"

# Reset failed status to retry
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "UPDATE pending_withdrawals SET status='pending', retry_count=0 WHERE status='failed'"
```

---

## Monitoring

### Check Pending Withdrawals

```bash
# Quick count
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT COUNT(*) FROM pending_withdrawals WHERE status='pending'"

# Detailed status
/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py --status
```

### Check Cron is Running

```bash
# View cron logs
tail -20 /root/Cloudflare_MT_Integration/logs/withdrawal_cron.log

# Check last run time
ls -la /root/Cloudflare_MT_Integration/logs/withdrawal_cron.log

# Verify cron job is installed
cat /etc/cron.d/cloudflare-mt-withdrawals
```

### Check for Errors

```bash
# Failed withdrawals
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT prefix, last_error, retry_count FROM pending_withdrawals WHERE status='failed'"

# Failed in history
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT prefix, withdrawn_at, notes FROM withdrawal_history WHERE status='failed'"
```

### Daily Statistics

```bash
# Events by type today
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT event_type, COUNT(*) FROM attack_events
   WHERE date(created_at) = date('now')
   GROUP BY event_type"

# Withdrawals today
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT COUNT(*), withdraw_method FROM withdrawal_history
   WHERE date(withdrawn_at) = date('now')
   GROUP BY withdraw_method"
```

### Network Analytics Events

```bash
# Recent Network Analytics events
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT event_datetime, attack_vector, source_ip, destination_port, packets
   FROM network_analytics_events
   ORDER BY id DESC LIMIT 10"

# Events by attack vector
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT attack_vector, COUNT(*), SUM(packets) as total_packets
   FROM network_analytics_events
   GROUP BY attack_vector
   ORDER BY total_packets DESC"

# Events today
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT COUNT(*) FROM network_analytics_events
   WHERE date(notified_at) = date('now')"

# Top source IPs
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
  "SELECT source_ip, COUNT(*), SUM(packets) as total_packets
   FROM network_analytics_events
   GROUP BY source_ip
   ORDER BY total_packets DESC
   LIMIT 10"
```

---

## Troubleshooting

### Withdrawal Not Processing

1. **Check if pending exists**:
   ```bash
   /root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py --status
   ```

2. **Check withdraw_after time**:
   ```bash
   sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db \
     "SELECT prefix, withdraw_after, datetime('now') as now FROM pending_withdrawals"
   ```

3. **Manually trigger check**:
   ```bash
   /root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py
   ```

4. **Check cron logs**:
   ```bash
   tail -50 /root/Cloudflare_MT_Integration/logs/withdrawal_cron.log
   ```

### Database Locked Error

```bash
# Check for processes using the database
fuser /root/Cloudflare_MT_Integration/db/magic_transit.db

# If stuck, restart webhook service
systemctl restart cloudflare-webhook
```

### Reset Database

```bash
# Backup first!
cp /root/Cloudflare_MT_Integration/db/magic_transit.db \
   /root/Cloudflare_MT_Integration/db/magic_transit.db.bak

# Delete and reinitialize
rm /root/Cloudflare_MT_Integration/db/magic_transit.db
python3 -c "from scripts.db_manager import init_database; init_database()"
```

### Manually Complete a Stuck Withdrawal

```bash
# Mark as completed (move to history)
python3 << 'EOF'
import sys
sys.path.insert(0, '/root/Cloudflare_MT_Integration/scripts')
from db_manager import mark_withdrawn
# Replace 1 with the actual record ID
mark_withdrawn(1, success=True, method='manual')
print("Done")
EOF
```

---

## Backup

### Database File Location

```
/root/Cloudflare_MT_Integration/db/magic_transit.db
```

### Backup Commands

```bash
# Simple copy
cp /root/Cloudflare_MT_Integration/db/magic_transit.db \
   /root/Cloudflare_MT_Integration/backup/magic_transit_$(date +%Y%m%d_%H%M%S).db

# SQLite dump (portable)
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db .dump > \
   /root/Cloudflare_MT_Integration/backup/magic_transit_$(date +%Y%m%d_%H%M%S).sql
```

### Restore from Backup

```bash
# From .db file
cp /root/Cloudflare_MT_Integration/backup/magic_transit_YYYYMMDD_HHMMSS.db \
   /root/Cloudflare_MT_Integration/db/magic_transit.db

# From .sql dump
sqlite3 /root/Cloudflare_MT_Integration/db/magic_transit.db < backup.sql
```

---

## Telegram Notifications

### Scheduled Withdrawal Success

```
🛡️ *CLOUDFLARE DDoS PROTECTION*

🔚 *SCHEDULED BGP WITHDRAWAL*

✅ *Status:* PREFIX WITHDRAWN
🎯 *Method:* Auto-scheduled (15min constraint)

📡 *PREFIX INFO*
📍 *CIDR:* `185.54.82.0/24`

⏱️ *TIMING*
🕐 *Withdrawn at:* 2026-01-19 01:00:00 UTC
⏳ *BGP Withdrawal:* ~15 minutes

🔄 *BGP STATUS*
🔙 Traffic returning to origin path
⚠️ Direct routing resumed
📊 Magic Transit protection disabled

🤖 *Operator:* Scheduled Task (Auto)

🏢 *GOLINE SOC* | _Magic Transit On-Demand_
```

### Scheduled Withdrawal Failed

```
🛡️ *CLOUDFLARE DDoS PROTECTION*

❌ *SCHEDULED WITHDRAWAL FAILED*

❌ *Status:* WITHDRAWAL FAILED
🎯 *Method:* Auto-scheduled

📡 *PREFIX INFO*
📍 *CIDR:* `185.54.82.0/24`

❌ *ERROR*
`API Error: rate limit exceeded`

⚠️ *Action Required:* Manual intervention needed

🤖 *Operator:* Scheduled Task (Auto)

🏢 *GOLINE SOC* | _Magic Transit On-Demand_
```

---

## Related Files

| File | Description |
|------|-------------|
| `/root/Cloudflare_MT_Integration/db/magic_transit.db` | SQLite database |
| `/root/Cloudflare_MT_Integration/scripts/db_manager.py` | Database module (v1.2.0) |
| `/root/Cloudflare_MT_Integration/scripts/cloudflare-check-pending-withdrawals.py` | Cron checker (DEPRECATED) |
| `/root/Cloudflare_MT_Integration/scripts/import_webhooks.py` | Webhook import tool |
| `/root/Cloudflare_MT_Integration/scripts/cloudflare-webhook-receiver.py` | Webhook (v1.6.0) |
| `/root/Cloudflare_MT_Integration/scripts/cloudflare-network-analytics-monitor.py` | Network Analytics (v1.3.1 - GeoIP) |
| `/root/Cloudflare_MT_Integration/scripts/cloudflare-autowithdraw.py` | Auto-withdraw daemon (v3.0) |
| `/etc/cron.d/cloudflare-mt-withdrawals` | Cron job config |
| `/root/Cloudflare_MT_Integration/logs/withdrawal_checker.log` | Checker logs |
| `/root/Cloudflare_MT_Integration/logs/withdrawal_cron.log` | Cron output |

---

*Documentation v1.2.0 - 2026-01-19 - GOLINE SA*
