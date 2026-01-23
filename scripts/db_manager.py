#!/usr/bin/env python3
"""
Database Manager for Cloudflare Magic Transit Integration
Handles pending BGP withdrawals, attack history tracking, and webhook storage.

Database: /root/Cloudflare_MT_Integration/db/magic_transit.db
Version: 1.3.0

Changelog:
- 1.3.0: Fixed attack_vector extraction for MNM alerts (use attack_type as fallback)
- 1.2.0: Added retry logic for failed withdrawals, cleanup for stale records,
         improved NULL handling, added get_failed_withdrawals(), cleanup_stale_pending()
- 1.1.0: Added webhook_events table
- 1.0.0: Initial version
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

# Database path
DB_DIR = Path("/root/Cloudflare_MT_Integration/db")
DB_PATH = DB_DIR / "magic_transit.db"


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database schema."""
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    # Pending withdrawals table
    # Note: UNIQUE constraint uses COALESCE to handle NULL attack_id properly
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL,
            attack_id TEXT,
            policy_id TEXT,
            policy_name TEXT,
            target_ip TEXT,
            attack_type TEXT,
            advertised_at DATETIME,
            withdraw_after DATETIME NOT NULL,
            attack_ended_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 5,
            next_retry_at DATETIME,
            last_error TEXT
        )
    ''')

    # Create unique index that handles NULL attack_id properly
    # Uses COALESCE to treat NULL as empty string for uniqueness
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_unique
        ON pending_withdrawals(prefix, COALESCE(attack_id, ''))
    ''')

    # Withdrawal history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL,
            attack_id TEXT,
            policy_id TEXT,
            policy_name TEXT,
            target_ip TEXT,
            attack_type TEXT,
            advertised_at DATETIME,
            attack_ended_at DATETIME,
            withdrawn_at DATETIME,
            attack_duration_seconds INTEGER,
            protection_duration_seconds INTEGER,
            withdraw_method TEXT,
            status TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Attack events log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            alert_type TEXT,
            attack_id TEXT,
            policy_id TEXT,
            policy_name TEXT,
            prefix TEXT,
            target_ip TEXT,
            target_port INTEGER,
            protocol TEXT,
            attack_vector TEXT,
            packets_per_second TEXT,
            megabits_per_second TEXT,
            severity TEXT,
            action_taken TEXT,
            raw_payload TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Webhook events table - stores ALL received webhooks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            alert_type TEXT,
            event_state TEXT,
            alert_id TEXT,
            policy_id TEXT,
            policy_name TEXT,
            target_ip TEXT,
            target_prefix TEXT,
            source_ip TEXT,
            processed INTEGER DEFAULT 1,
            action_taken TEXT,
            payload JSON,
            UNIQUE(alert_id, event_state)
        )
    ''')

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_withdrawals(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_withdraw_after ON pending_withdrawals(withdraw_after)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_prefix ON withdrawal_history(prefix)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_attack_id ON attack_events(attack_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_webhook_alert_type ON webhook_events(alert_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_webhook_received_at ON webhook_events(received_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_webhook_target_ip ON webhook_events(target_ip)')

    conn.commit()
    conn.close()

    return True


def add_pending_withdrawal(prefix, withdraw_after, attack_id=None, policy_id=None,
                          policy_name=None, target_ip=None, attack_type=None,
                          advertised_at=None, attack_ended_at=None):
    """
    Add a pending withdrawal to the database.
    Returns the record ID or None if already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO pending_withdrawals
            (prefix, attack_id, policy_id, policy_name, target_ip, attack_type,
             advertised_at, withdraw_after, attack_ended_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (prefix, attack_id, policy_id, policy_name, target_ip, attack_type,
              advertised_at, withdraw_after, attack_ended_at))

        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    except sqlite3.IntegrityError:
        # Already exists (same prefix + attack_id)
        conn.close()
        return None


def get_pending_withdrawals():
    """
    Get all pending withdrawals that are ready to be processed.
    Includes:
    - Pending withdrawals where withdraw_after <= now
    - Failed withdrawals that are ready for retry (next_retry_at <= now AND retry_count < max_retries)
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        SELECT * FROM pending_withdrawals
        WHERE (status = 'pending' AND withdraw_after <= ?)
           OR (status = 'failed' AND retry_count < max_retries
               AND (next_retry_at IS NULL OR next_retry_at <= ?))
        ORDER BY withdraw_after ASC
    ''', (now, now))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_failed_withdrawals():
    """Get all failed withdrawals (for reporting/manual intervention)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM pending_withdrawals
        WHERE status = 'failed'
        ORDER BY created_at DESC
    ''')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_all_pending():
    """Get all pending withdrawals (regardless of time)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM pending_withdrawals
        WHERE status = 'pending'
        ORDER BY withdraw_after ASC
    ''')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def mark_withdrawn(record_id, success=True, error=None, method='auto'):
    """
    Mark a pending withdrawal as completed and move to history.
    On failure: increments retry_count, sets next_retry_at with exponential backoff.
    If max_retries exceeded: moves to history with 'max_retries_exceeded' status.
    """
    from datetime import timedelta

    conn = get_connection()
    cursor = conn.cursor()

    # Get the pending record
    cursor.execute('SELECT * FROM pending_withdrawals WHERE id = ?', (record_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False

    record = dict(row)
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Calculate durations
    attack_duration = None
    protection_duration = None

    if record['advertised_at'] and record['attack_ended_at']:
        try:
            adv_time = datetime.fromisoformat(record['advertised_at'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(record['attack_ended_at'].replace('Z', '+00:00'))
            attack_duration = int((end_time - adv_time).total_seconds())
        except:
            pass

    if record['advertised_at']:
        try:
            adv_time = datetime.fromisoformat(record['advertised_at'].replace('Z', '+00:00'))
            protection_duration = int((now - adv_time).total_seconds())
        except:
            pass

    if success:
        # Success: move to history and delete from pending
        cursor.execute('''
            INSERT INTO withdrawal_history
            (prefix, attack_id, policy_id, policy_name, target_ip, attack_type,
             advertised_at, attack_ended_at, withdrawn_at, attack_duration_seconds,
             protection_duration_seconds, withdraw_method, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', ?)
        ''', (record['prefix'], record['attack_id'], record['policy_id'],
              record['policy_name'], record['target_ip'], record['attack_type'],
              record['advertised_at'], record['attack_ended_at'], now_str,
              attack_duration, protection_duration, method, None))

        cursor.execute('DELETE FROM pending_withdrawals WHERE id = ?', (record_id,))

    else:
        # Failure: check if we should retry or give up
        new_retry_count = record['retry_count'] + 1
        max_retries = record.get('max_retries', 5) or 5

        if new_retry_count >= max_retries:
            # Max retries exceeded: move to history with failed status
            cursor.execute('''
                INSERT INTO withdrawal_history
                (prefix, attack_id, policy_id, policy_name, target_ip, attack_type,
                 advertised_at, attack_ended_at, withdrawn_at, attack_duration_seconds,
                 protection_duration_seconds, withdraw_method, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'max_retries_exceeded', ?)
            ''', (record['prefix'], record['attack_id'], record['policy_id'],
                  record['policy_name'], record['target_ip'], record['attack_type'],
                  record['advertised_at'], record['attack_ended_at'], now_str,
                  attack_duration, protection_duration, method,
                  f"Failed after {new_retry_count} retries. Last error: {error}"))

            cursor.execute('DELETE FROM pending_withdrawals WHERE id = ?', (record_id,))

        else:
            # Schedule retry with exponential backoff: 5min, 10min, 20min, 40min, 80min
            backoff_minutes = 5 * (2 ** record['retry_count'])  # 5, 10, 20, 40, 80
            next_retry = now + timedelta(minutes=backoff_minutes)
            next_retry_str = next_retry.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE pending_withdrawals
                SET status = 'failed',
                    retry_count = ?,
                    next_retry_at = ?,
                    last_error = ?
                WHERE id = ?
            ''', (new_retry_count, next_retry_str, error, record_id))

    conn.commit()
    conn.close()

    return True


def log_attack_event(event_type, payload, prefix=None, action_taken=None):
    """
    Log an attack event (START or END) to the database.

    Handles both DDoS alerts (attack_vector) and MNM alerts (attack_type).
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    data = payload.get('data', {})

    # Handle both DDoS (attack_vector) and MNM (attack_type) alerts
    attack_vector = data.get('attack_vector') or data.get('attack_type')

    cursor.execute('''
        INSERT INTO attack_events
        (event_type, alert_type, attack_id, policy_id, policy_name, prefix,
         target_ip, target_port, protocol, attack_vector, packets_per_second,
         megabits_per_second, severity, action_taken, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event_type,
        payload.get('alert_type'),
        data.get('attack_id'),
        payload.get('policy_id'),
        payload.get('policy_name'),
        prefix,
        data.get('target_ip'),
        data.get('target_port'),
        data.get('protocol'),
        attack_vector,
        str(data.get('packets_per_second', '')),
        str(data.get('megabits_per_second', '')),
        data.get('severity'),
        action_taken,
        json.dumps(payload)
    ))

    conn.commit()
    conn.close()


def get_attack_history(limit=50):
    """Get recent attack history."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM withdrawal_history
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_attack_events(limit=100):
    """Get recent attack events."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, event_type, alert_type, attack_id, policy_name, prefix,
               target_ip, severity, action_taken, created_at
        FROM attack_events
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def cleanup_stale_pending(max_age_hours=24):
    """
    Clean up stale pending withdrawals older than max_age_hours.
    Moves them to history with status 'stale_cleaned'.
    Returns count of cleaned records.
    """
    from datetime import timedelta

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Find stale records
    cursor.execute('''
        SELECT * FROM pending_withdrawals
        WHERE created_at < ?
    ''', (cutoff_str,))

    rows = cursor.fetchall()
    cleaned_count = 0

    for row in rows:
        record = dict(row)

        # Move to history
        cursor.execute('''
            INSERT INTO withdrawal_history
            (prefix, attack_id, policy_id, policy_name, target_ip, attack_type,
             advertised_at, attack_ended_at, withdrawn_at, attack_duration_seconds,
             protection_duration_seconds, withdraw_method, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'auto_cleanup', 'stale_cleaned', ?)
        ''', (record['prefix'], record['attack_id'], record['policy_id'],
              record['policy_name'], record['target_ip'], record['attack_type'],
              record['advertised_at'], record['attack_ended_at'], now_str,
              f"Cleaned after {max_age_hours}h. Last error: {record.get('last_error', 'N/A')}"))

        # Delete from pending
        cursor.execute('DELETE FROM pending_withdrawals WHERE id = ?', (record['id'],))
        cleaned_count += 1

    conn.commit()
    conn.close()

    return cleaned_count


def reset_failed_for_retry(record_id):
    """
    Reset a failed withdrawal to pending status for immediate retry.
    Useful for manual intervention.
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        UPDATE pending_withdrawals
        SET status = 'pending',
            withdraw_after = ?,
            next_retry_at = NULL,
            last_error = 'Manual reset for retry'
        WHERE id = ? AND status = 'failed'
    ''', (now, record_id))

    affected = cursor.rowcount
    conn.commit()
    conn.close()

    return affected > 0


def get_stats():
    """Get database statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Pending count
    cursor.execute('SELECT COUNT(*) FROM pending_withdrawals WHERE status = "pending"')
    stats['pending_withdrawals'] = cursor.fetchone()[0]

    # Total withdrawals
    cursor.execute('SELECT COUNT(*) FROM withdrawal_history')
    stats['total_withdrawals'] = cursor.fetchone()[0]

    # Successful withdrawals
    cursor.execute('SELECT COUNT(*) FROM withdrawal_history WHERE status = "success"')
    stats['successful_withdrawals'] = cursor.fetchone()[0]

    # Total attack events
    cursor.execute('SELECT COUNT(*) FROM attack_events')
    stats['total_events'] = cursor.fetchone()[0]

    # Events today
    cursor.execute('''
        SELECT COUNT(*) FROM attack_events
        WHERE date(created_at) = date('now')
    ''')
    stats['events_today'] = cursor.fetchone()[0]

    # Webhook stats
    cursor.execute('SELECT COUNT(*) FROM webhook_events')
    stats['total_webhooks'] = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM webhook_events
        WHERE date(received_at) = date('now')
    ''')
    stats['webhooks_today'] = cursor.fetchone()[0]

    conn.close()

    return stats


# ============================================================
# WEBHOOK EVENTS FUNCTIONS
# ============================================================

def log_webhook_event(payload, source_ip=None, action_taken=None, target_prefix=None):
    """
    Log a webhook event to the database.
    Returns the record ID or None if duplicate.
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    data = payload.get('data', {})

    # Extract alert_id from various possible locations
    alert_id = (
        data.get('attack_id') or
        data.get('alert_id') or
        data.get('incident_id') or
        data.get('tunnel_id') or
        data.get('health_check_id') or
        payload.get('alert_correlation_id') or
        # Generate fallback ID from timestamp
        f"webhook-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    )

    # Extract target IP
    target_ip = data.get('target_ip') or data.get('target_hostname') or None

    try:
        cursor.execute('''
            INSERT INTO webhook_events
            (alert_type, event_state, alert_id, policy_id, policy_name,
             target_ip, target_prefix, source_ip, processed, action_taken, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ''', (
            payload.get('alert_type'),
            payload.get('alert_event'),
            alert_id,
            payload.get('policy_id'),
            payload.get('policy_name'),
            target_ip,
            target_prefix,
            source_ip,
            action_taken,
            json.dumps(payload)
        ))

        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    except sqlite3.IntegrityError:
        # Duplicate webhook (same alert_id + event_state)
        conn.close()
        return None


def get_webhook_events(limit=100, alert_type=None, days=None):
    """
    Get webhook events with optional filters.

    Args:
        limit: Maximum number of records to return
        alert_type: Filter by alert_type (e.g., 'advanced_ddos_attack_l4_alert')
        days: Filter to last N days only
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM webhook_events WHERE 1=1'
    params = []

    if alert_type:
        query += ' AND alert_type = ?'
        params.append(alert_type)

    if days:
        query += ' AND received_at >= datetime("now", ?)'
        params.append(f'-{days} days')

    query += ' ORDER BY received_at DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_webhook_by_alert_id(alert_id):
    """Get all webhook events for a specific alert_id (correlates START/END)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM webhook_events
        WHERE alert_id = ?
        ORDER BY received_at ASC
    ''', (alert_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_webhook_stats():
    """Get webhook-specific statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Total webhooks
    cursor.execute('SELECT COUNT(*) FROM webhook_events')
    stats['total'] = cursor.fetchone()[0]

    # Today
    cursor.execute('''
        SELECT COUNT(*) FROM webhook_events
        WHERE date(received_at) = date('now')
    ''')
    stats['today'] = cursor.fetchone()[0]

    # Last 7 days
    cursor.execute('''
        SELECT COUNT(*) FROM webhook_events
        WHERE received_at >= datetime('now', '-7 days')
    ''')
    stats['last_7_days'] = cursor.fetchone()[0]

    # By alert_type
    cursor.execute('''
        SELECT alert_type, COUNT(*) as count
        FROM webhook_events
        GROUP BY alert_type
        ORDER BY count DESC
    ''')
    stats['by_type'] = {row['alert_type']: row['count'] for row in cursor.fetchall()}

    # By event_state
    cursor.execute('''
        SELECT event_state, COUNT(*) as count
        FROM webhook_events
        WHERE event_state IS NOT NULL
        GROUP BY event_state
    ''')
    stats['by_state'] = {row['event_state']: row['count'] for row in cursor.fetchall()}

    # Attack correlations (START with END)
    cursor.execute('''
        SELECT COUNT(DISTINCT w1.alert_id) as count
        FROM webhook_events w1
        WHERE w1.event_state = 'ALERT_STATE_EVENT_START'
        AND EXISTS (
            SELECT 1 FROM webhook_events w2
            WHERE w2.alert_id = w1.alert_id
            AND w2.event_state = 'ALERT_STATE_EVENT_END'
        )
    ''')
    stats['completed_attacks'] = cursor.fetchone()[0]

    conn.close()

    return stats


def import_webhook_from_json(json_file_path, source_ip=None):
    """
    Import a webhook from a JSON file.
    Returns (success, record_id or error message)
    """
    import json

    try:
        with open(json_file_path, 'r') as f:
            payload = json.load(f)

        record_id = log_webhook_event(payload, source_ip=source_ip, action_taken='imported')

        if record_id:
            return True, record_id
        else:
            return False, "Duplicate webhook (already imported)"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error: {e}"


# Initialize database on import
if not DB_PATH.exists():
    init_database()
