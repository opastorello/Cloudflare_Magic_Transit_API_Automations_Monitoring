# Database Manager

**Script**: `db_manager.py`
**Version**: 1.3.0
**Last Updated**: 2026-01-22

---

## Overview

Python module providing all database operations for the Cloudflare Magic Transit Integration system. Handles event logging, withdrawal tracking, webhook storage, and statistics.

### Key Features

| Feature | Description |
|---------|-------------|
| **Schema Management** | Auto-initializes database tables and indexes |
| **Attack Events** | Logs START/END/WITHDRAW events |
| **Withdrawal Tracking** | Manages pending withdrawals with retry logic |
| **Webhook Storage** | Stores all received webhooks |
| **Deduplication** | Prevents duplicate entries via unique constraints |
| **Retry Logic** | Exponential backoff for failed withdrawals |
| **Statistics** | Aggregated stats for monitoring |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE MANAGER FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  cloudflare-webhook-receiver.py                                              │
│  ├── log_attack_event(START/END)                                            │
│  └── log_webhook_event()                                                    │
│                                                                              │
│  cloudflare-autowithdraw.py                                                  │
│  └── log_attack_event(WITHDRAW) + withdrawal_history                        │
│                                                                              │
│  cloudflare-network-analytics-monitor.py                                     │
│  └── [Uses own table: network_analytics_events]                             │
│                                                                              │
│                              ↓                                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      db_manager.py                                   │    │
│  │                                                                      │    │
│  │  Tables:                                                             │    │
│  │  ├── attack_events        → All START/END/WITHDRAW events           │    │
│  │  ├── withdrawal_history   → Completed withdrawals                   │    │
│  │  ├── pending_withdrawals  → Queue for scheduled withdrawals (DEPRECATED) │
│  │  └── webhook_events       → All received webhooks                   │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ↓                                               │
│                      magic_transit.db                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Location

```
/root/Cloudflare_MT_Integration/db/magic_transit.db
```

**Type**: SQLite 3
**Auto-Initialize**: Creates tables on first import if database doesn't exist

---

## Tables

### 1. attack_events

Logs all attack-related events (START, END, WITHDRAW).

```sql
CREATE TABLE attack_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,         -- 'START', 'END', 'WITHDRAW'
    alert_type TEXT,                   -- Cloudflare alert type
    attack_id TEXT,                    -- Cloudflare attack ID
    policy_id TEXT,                    -- DDoS policy ID
    policy_name TEXT,                  -- DDoS policy name
    prefix TEXT,                       -- BGP prefix affected
    target_ip TEXT,                    -- Target IP address
    target_port INTEGER,               -- Target port
    protocol TEXT,                     -- TCP/UDP
    attack_vector TEXT,                -- SYN Flood, UDP Flood, etc.
    packets_per_second TEXT,           -- Attack volume (pps)
    megabits_per_second TEXT,          -- Attack volume (Mbps)
    severity TEXT,                     -- Attack severity
    action_taken TEXT,                 -- Action performed
    raw_payload TEXT,                  -- Full JSON payload
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2. withdrawal_history

Records of completed BGP withdrawals.

```sql
CREATE TABLE withdrawal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prefix TEXT NOT NULL,
    attack_id TEXT,
    policy_id TEXT,
    policy_name TEXT,
    target_ip TEXT,
    attack_type TEXT,
    advertised_at DATETIME,            -- When prefix was advertised
    attack_ended_at DATETIME,          -- When attack ended
    withdrawn_at DATETIME,             -- When prefix was withdrawn
    attack_duration_seconds INTEGER,   -- Duration of attack
    protection_duration_seconds INTEGER, -- How long prefix was protected
    withdraw_method TEXT,              -- 'auto', 'manual', 'autowithdraw_daemon'
    status TEXT,                       -- 'success', 'max_retries_exceeded', 'stale_cleaned'
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3. pending_withdrawals (DEPRECATED)

**Note**: This table is deprecated since v2.1.0. All withdrawals are now handled by `cloudflare-autowithdraw.service`.

```sql
CREATE TABLE pending_withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prefix TEXT NOT NULL,
    attack_id TEXT,
    policy_id TEXT,
    policy_name TEXT,
    target_ip TEXT,
    attack_type TEXT,
    advertised_at DATETIME,
    withdraw_after DATETIME NOT NULL,  -- When withdrawal is allowed
    attack_ended_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',     -- 'pending', 'failed'
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    next_retry_at DATETIME,
    last_error TEXT
);
```

### 4. webhook_events

Stores all received webhooks for audit and correlation.

```sql
CREATE TABLE webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT,                   -- Cloudflare alert type
    event_state TEXT,                  -- 'ALERT_STATE_EVENT_START' or 'ALERT_STATE_EVENT_END'
    alert_id TEXT,                     -- Unique alert identifier
    policy_id TEXT,
    policy_name TEXT,
    target_ip TEXT,
    target_prefix TEXT,
    source_ip TEXT,                    -- Source IP of webhook request
    processed INTEGER DEFAULT 1,
    action_taken TEXT,
    payload JSON,                      -- Full webhook payload
    UNIQUE(alert_id, event_state)      -- Prevents duplicates
);
```

---

## Functions Reference

### Connection

```python
get_connection() -> sqlite3.Connection
```
Returns a database connection with row factory enabled.

### Schema

```python
init_database() -> bool
```
Initializes all tables and indexes. Called automatically on import if database doesn't exist.

---

### Attack Events

```python
log_attack_event(event_type, payload, prefix=None, action_taken=None)
```
Logs a START, END, or WITHDRAW event.

**Parameters**:
- `event_type`: 'START', 'END', or 'WITHDRAW'
- `payload`: Webhook payload dict
- `prefix`: BGP prefix (optional)
- `action_taken`: Description of action taken

```python
get_attack_events(limit=100) -> list[dict]
```
Returns recent attack events.

```python
get_attack_history(limit=50) -> list[dict]
```
Returns withdrawal history records.

---

### Pending Withdrawals (Deprecated)

**Note**: These functions are deprecated since v2.1.0 but remain for backward compatibility.

```python
add_pending_withdrawal(prefix, withdraw_after, attack_id=None, ...) -> int|None
```
Adds a pending withdrawal. Returns record ID or None if duplicate.

```python
get_pending_withdrawals() -> list[dict]
```
Returns withdrawals ready to be processed (withdraw_after <= now or failed with retries remaining).

```python
get_all_pending() -> list[dict]
```
Returns all pending withdrawals regardless of time.

```python
get_failed_withdrawals() -> list[dict]
```
Returns all failed withdrawals for manual intervention.

```python
mark_withdrawn(record_id, success=True, error=None, method='auto') -> bool
```
Marks a withdrawal as completed. On success, moves to history. On failure, schedules retry with exponential backoff.

**Exponential Backoff**: 5min, 10min, 20min, 40min, 80min

```python
cleanup_stale_pending(max_age_hours=24) -> int
```
Cleans up stale pending withdrawals older than specified hours.

```python
reset_failed_for_retry(record_id) -> bool
```
Resets a failed withdrawal for immediate retry.

---

### Webhook Events

```python
log_webhook_event(payload, source_ip=None, action_taken=None, target_prefix=None) -> int|None
```
Logs a webhook event. Returns record ID or None if duplicate.

```python
get_webhook_events(limit=100, alert_type=None, days=None) -> list[dict]
```
Returns webhook events with optional filters.

**Parameters**:
- `limit`: Maximum records to return
- `alert_type`: Filter by alert type
- `days`: Filter to last N days

```python
get_webhook_by_alert_id(alert_id) -> list[dict]
```
Returns all webhooks for an alert ID (correlates START/END events).

```python
get_webhook_stats() -> dict
```
Returns webhook statistics:
- `total`: Total webhooks
- `today`: Webhooks today
- `last_7_days`: Webhooks in last 7 days
- `by_type`: Count by alert_type
- `by_state`: Count by event_state
- `completed_attacks`: Attacks with both START and END

```python
import_webhook_from_json(json_file_path, source_ip=None) -> tuple[bool, int|str]
```
Imports a webhook from JSON file. Returns (success, record_id or error message).

---

### Statistics

```python
get_stats() -> dict
```
Returns database statistics:
- `pending_withdrawals`: Count of pending withdrawals
- `total_withdrawals`: Total withdrawal history
- `successful_withdrawals`: Successful withdrawals
- `total_events`: Total attack events
- `events_today`: Events today
- `total_webhooks`: Total webhooks
- `webhooks_today`: Webhooks today

---

## Usage Examples

### In Other Scripts

```python
from db_manager import (
    log_attack_event,
    log_webhook_event,
    get_stats
)

# Log an attack event
log_attack_event('START', payload, prefix='185.54.81.0/24', action_taken='notified')

# Log a webhook
log_webhook_event(payload, source_ip='162.159.76.0', action_taken='processed')

# Get statistics
stats = get_stats()
print(f"Events today: {stats['events_today']}")
```

### From Command Line

```bash
# Recent attack events
sqlite3 db/magic_transit.db "SELECT event_type, prefix, created_at FROM attack_events ORDER BY id DESC LIMIT 10;"

# Withdrawal history
sqlite3 db/magic_transit.db "SELECT prefix, withdrawn_at, protection_duration_seconds/60 as minutes, withdraw_method FROM withdrawal_history ORDER BY id DESC LIMIT 10;"

# Webhook stats
sqlite3 db/magic_transit.db "SELECT alert_type, COUNT(*) as count FROM webhook_events GROUP BY alert_type;"

# Events today
sqlite3 db/magic_transit.db "SELECT * FROM attack_events WHERE date(created_at) = date('now');"
```

---

## Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| `idx_pending_unique` | pending_withdrawals | prefix, COALESCE(attack_id, '') | Prevent duplicates |
| `idx_pending_status` | pending_withdrawals | status | Filter by status |
| `idx_pending_withdraw_after` | pending_withdrawals | withdraw_after | Time-based queries |
| `idx_history_prefix` | withdrawal_history | prefix | Filter by prefix |
| `idx_events_attack_id` | attack_events | attack_id | Correlation queries |
| `idx_webhook_alert_type` | webhook_events | alert_type | Filter by type |
| `idx_webhook_received_at` | webhook_events | received_at | Time-based queries |
| `idx_webhook_target_ip` | webhook_events | target_ip | Filter by target |

---

## Integration with v2.1.0 Architecture

Since v2.1.0, the database is used as follows:

| Component | Tables Used | Operations |
|-----------|-------------|------------|
| `cloudflare-webhook-receiver.py` | attack_events, webhook_events | INSERT (START/END events) |
| `cloudflare-autowithdraw.py` | attack_events, withdrawal_history | INSERT (WITHDRAW events) |
| `cloudflare-network-analytics-monitor.py` | network_analytics_events | INSERT (separate table) |
| `cloudflare-check-pending-withdrawals.py` | pending_withdrawals | **DEPRECATED** |

**Important**: The `pending_withdrawals` table is no longer actively used. All BGP withdrawals are performed by `cloudflare-autowithdraw.service` based on real-time GraphQL traffic analysis.

---

## Maintenance

### Backup

```bash
# Create backup
cp db/magic_transit.db db/magic_transit.db.backup.$(date +%Y%m%d)

# Verify integrity
sqlite3 db/magic_transit.db "PRAGMA integrity_check;"
```

### Cleanup

```bash
# Vacuum database
sqlite3 db/magic_transit.db "VACUUM;"

# Clear old webhook events (keep last 30 days)
sqlite3 db/magic_transit.db "DELETE FROM webhook_events WHERE received_at < datetime('now', '-30 days');"

# Clear old attack events (keep last 90 days)
sqlite3 db/magic_transit.db "DELETE FROM attack_events WHERE created_at < datetime('now', '-90 days');"
```

### View Schema

```bash
# List tables
sqlite3 db/magic_transit.db ".tables"

# Show table schema
sqlite3 db/magic_transit.db ".schema attack_events"
sqlite3 db/magic_transit.db ".schema webhook_events"
```

---

## Changelog

### v1.3.0 (2026-01-21)
- **FIX**: `log_attack_event()` now uses `attack_type` as fallback if `attack_vector` not present in MNM alerts
- **Integration**: Added support for `prefix_calm_status` table (used by autowithdraw daemon)

### v1.2.0 (2026-01-19)
- Added retry logic for failed withdrawals (exponential backoff)
- Added `cleanup_stale_pending()` function
- Added `get_failed_withdrawals()` function
- Improved NULL handling with COALESCE in unique index
- Note: `pending_withdrawals` deprecated in v2.1.0 architecture

### v1.1.0
- Added `webhook_events` table
- Added webhook-related functions
- Added `get_webhook_stats()` for analytics

### v1.0.0
- Initial version
- Basic tables: attack_events, withdrawal_history, pending_withdrawals

---

## Related Documentation

- [DATABASE.md](DATABASE.md) - Database architecture overview
- [AUTOWITHDRAW.md](AUTOWITHDRAW.md) - Auto-withdraw daemon (uses attack_events + withdrawal_history)
- [WEBHOOK_RECEIVER.md](WEBHOOK_RECEIVER.md) - Webhook receiver (uses attack_events + webhook_events)

---

*GOLINE SOC - Cloudflare Magic Transit Integration*
