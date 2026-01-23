#!/usr/bin/env python3
"""
Import existing webhook JSON files into the database.

Usage:
    python3 import_webhooks.py                    # Import all from logs/webhooks/
    python3 import_webhooks.py --file file.json  # Import single file
    python3 import_webhooks.py --dry-run         # Show what would be imported
    python3 import_webhooks.py --stats           # Show database stats

Version: 1.0.0
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from db_manager import (
    init_database, import_webhook_from_json, get_webhook_stats, get_webhook_events
)

# Default webhook directory
WEBHOOK_DIR = Path("/root/Cloudflare_MT_Integration/logs/webhooks")


def import_all_webhooks(dry_run=False):
    """Import all webhook JSON files from the logs directory."""
    if not WEBHOOK_DIR.exists():
        print(f"Webhook directory not found: {WEBHOOK_DIR}")
        return

    json_files = sorted(WEBHOOK_DIR.glob("webhook_*.json"))

    if not json_files:
        print("No webhook JSON files found to import.")
        return

    print(f"Found {len(json_files)} webhook files to import")
    print("-" * 50)

    imported = 0
    skipped = 0
    errors = 0

    for json_file in json_files:
        filename = json_file.name

        if dry_run:
            print(f"  [DRY-RUN] Would import: {filename}")
            imported += 1
            continue

        success, result = import_webhook_from_json(str(json_file))

        if success:
            print(f"  [OK] Imported: {filename} -> DB ID {result}")
            imported += 1
        elif "Duplicate" in str(result):
            print(f"  [SKIP] Already exists: {filename}")
            skipped += 1
        else:
            print(f"  [ERROR] {filename}: {result}")
            errors += 1

    print("-" * 50)
    print(f"Summary: {imported} imported, {skipped} skipped, {errors} errors")


def import_single_file(filepath, dry_run=False):
    """Import a single webhook JSON file."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    if dry_run:
        print(f"[DRY-RUN] Would import: {filepath}")
        return

    success, result = import_webhook_from_json(filepath)

    if success:
        print(f"[OK] Imported: {filepath} -> DB ID {result}")
    elif "Duplicate" in str(result):
        print(f"[SKIP] Already exists: {filepath}")
    else:
        print(f"[ERROR] {filepath}: {result}")


def show_stats():
    """Show webhook database statistics."""
    stats = get_webhook_stats()

    print("\n" + "=" * 50)
    print("WEBHOOK DATABASE STATISTICS")
    print("=" * 50)

    print(f"\nTotal webhooks: {stats.get('total', 0)}")
    print(f"Today: {stats.get('today', 0)}")
    print(f"Last 7 days: {stats.get('last_7_days', 0)}")
    print(f"Completed attacks (START+END): {stats.get('completed_attacks', 0)}")

    print("\nBy Alert Type:")
    for alert_type, count in stats.get('by_type', {}).items():
        print(f"  {alert_type or 'unknown'}: {count}")

    print("\nBy Event State:")
    for state, count in stats.get('by_state', {}).items():
        print(f"  {state}: {count}")

    print("\n" + "=" * 50)


def show_recent(limit=10):
    """Show recent webhook events."""
    events = get_webhook_events(limit=limit)

    print("\n" + "=" * 80)
    print(f"RECENT WEBHOOK EVENTS (last {limit})")
    print("=" * 80)

    for event in events:
        received = event.get('received_at', 'N/A') or 'N/A'
        alert_type = event.get('alert_type', 'unknown') or 'unknown'
        event_state = event.get('event_state') or '-'
        target = event.get('target_ip') or 'N/A'

        # Shorten alert_type for display
        if len(alert_type) > 30:
            alert_type = alert_type[:27] + "..."

        print(f"  {received} | {alert_type:<30} | {event_state:<25} | {target}")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Import webhook JSON files into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 import_webhooks.py              # Import all webhooks
  python3 import_webhooks.py --dry-run    # Preview what would be imported
  python3 import_webhooks.py --stats      # Show database statistics
  python3 import_webhooks.py --recent 20  # Show 20 most recent webhooks
  python3 import_webhooks.py --file x.json  # Import single file
"""
    )

    parser.add_argument('--file', '-f', help='Import a single JSON file')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='Preview what would be imported')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--recent', '-r', type=int, metavar='N',
                       help='Show N most recent webhook events')

    args = parser.parse_args()

    # Initialize database
    init_database()

    if args.stats:
        show_stats()
    elif args.recent:
        show_recent(args.recent)
    elif args.file:
        import_single_file(args.file, dry_run=args.dry_run)
    else:
        import_all_webhooks(dry_run=args.dry_run)
        if not args.dry_run:
            print("\n")
            show_stats()


if __name__ == '__main__':
    main()
