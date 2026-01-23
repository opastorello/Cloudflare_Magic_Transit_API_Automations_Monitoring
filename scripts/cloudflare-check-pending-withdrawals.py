#!/usr/bin/env python3
"""
Check and process pending BGP prefix withdrawals.
Runs via cron every 5 minutes.

This script:
1. Cleans up stale pending withdrawals (>24h old)
2. Checks the database for pending withdrawals where withdraw_after <= now
3. Includes failed withdrawals ready for retry (with exponential backoff)
4. Verifies prefix status before withdrawal (avoids duplicate API calls)
5. Tracks processed prefixes to handle multiple entries for same prefix
6. Attempts to withdraw each prefix via Cloudflare API
7. Sends Telegram notification for each withdrawal
8. Updates database with results (including retry scheduling on failure)

Usage:
    ./check_pending_withdrawals.py           # Process pending withdrawals
    ./check_pending_withdrawals.py --status  # Show current status
    ./check_pending_withdrawals.py --history # Show withdrawal history
    ./check_pending_withdrawals.py --cleanup # Manual cleanup of stale records
    ./check_pending_withdrawals.py --failed  # Show failed withdrawals

Version: 1.2.0

Changelog:
- 1.2.0: Added auto-cleanup for stale records, retry logic with backoff,
         --cleanup and --failed options
- 1.1.0: Added duplicate prefix handling, prefix status check
- 1.0.0: Initial version
"""

import sys
import json
import logging
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from db_manager import (
    init_database, get_pending_withdrawals, get_all_pending,
    mark_withdrawn, get_stats, get_attack_history,
    cleanup_stale_pending, get_failed_withdrawals, reset_failed_for_retry
)

# Configuration
CONFIG_PATH = Path("/root/Cloudflare_MT_Integration/config/settings.json")
PREFIX_MAP_PATH = Path("/root/Cloudflare_MT_Integration/config/prefix_mapping.json")
LOG_PATH = Path("/root/Cloudflare_MT_Integration/logs/withdrawal_checker.log")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration files."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    with open(PREFIX_MAP_PATH) as f:
        prefix_mapping = json.load(f)
    return config, prefix_mapping


def check_prefix_status(prefix, config, prefix_mapping):
    """
    Check if a prefix is currently advertised.
    Returns (is_advertised, error_message).
    """
    if prefix not in prefix_mapping['prefixes']:
        return None, f"Prefix {prefix} not in mapping"

    prefix_info = prefix_mapping['prefixes'][prefix]

    if not prefix_info.get('bgp_prefix_id'):
        return None, f"Prefix {prefix} has no BGP prefix ID"

    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{config['cloudflare']['account_id']}/addressing/prefixes/"
           f"{prefix_info['prefix_id']}/bgp/prefixes/{prefix_info['bgp_prefix_id']}")

    headers = {
        "Authorization": f"Bearer {config['cloudflare']['api_token']}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            result = response.json().get('result', {})
            on_demand = result.get('on_demand', {})
            return on_demand.get('advertised', False), None
        else:
            error = response.json().get('errors', [{}])[0].get('message', response.text)
            return None, f"API Error: {error}"

    except requests.exceptions.Timeout:
        return None, "API Timeout"
    except Exception as e:
        return None, str(e)


def withdraw_prefix(prefix, config, prefix_mapping):
    """
    Withdraw a BGP prefix via Cloudflare API.
    Returns (success, error_message, already_withdrawn).
    """
    if prefix not in prefix_mapping['prefixes']:
        return False, f"Prefix {prefix} not in mapping", False

    prefix_info = prefix_mapping['prefixes'][prefix]

    if not prefix_info.get('bgp_prefix_id'):
        return False, f"Prefix {prefix} has no BGP prefix ID", False

    # First, check if prefix is already withdrawn
    is_advertised, check_error = check_prefix_status(prefix, config, prefix_mapping)

    if check_error:
        logger.warning(f"Could not check status for {prefix}: {check_error}")
        # Continue with withdrawal attempt anyway
    elif is_advertised is False:
        # Prefix is already withdrawn - no need to call API
        logger.info(f"Prefix {prefix} is already withdrawn - skipping API call")
        return True, None, True  # Success, no error, already_withdrawn=True

    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{config['cloudflare']['account_id']}/addressing/prefixes/"
           f"{prefix_info['prefix_id']}/bgp/prefixes/{prefix_info['bgp_prefix_id']}")

    headers = {
        "Authorization": f"Bearer {config['cloudflare']['api_token']}",
        "Content-Type": "application/json"
    }

    data = {"on_demand": {"advertised": False}}

    try:
        response = requests.patch(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            return True, None, False
        else:
            error = response.json().get('errors', [{}])[0].get('message', response.text)
            return False, f"API Error: {error}", False

    except requests.exceptions.Timeout:
        return False, "API Timeout", False
    except Exception as e:
        return False, str(e), False


def send_telegram_notification(message, config):
    """Send Telegram notification."""
    try:
        url = f"https://api.telegram.org/bot{config['telegram']['bot_token']}/sendMessage"
        data = {
            "chat_id": config['telegram']['chat_id'],
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def format_duration(seconds):
    """Format seconds as human-readable duration."""
    if seconds is None:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def process_pending_withdrawals():
    """Process all pending withdrawals that are ready."""
    # Initialize database if needed
    init_database()

    # First, cleanup stale pending withdrawals (>24h old)
    cleaned = cleanup_stale_pending(max_age_hours=24)
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} stale pending withdrawal(s)")

    # Load configuration
    try:
        config, prefix_mapping = load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Get pending withdrawals ready for processing (includes failed ready for retry)
    pending = get_pending_withdrawals()

    if not pending:
        logger.info("No pending withdrawals ready for processing")
        return 0

    logger.info(f"Found {len(pending)} pending withdrawal(s) to process")

    success_count = 0
    fail_count = 0
    results = []

    # Track prefixes already processed in this run to avoid duplicates
    processed_prefixes = set()

    for record in pending:
        prefix = record['prefix']
        attack_id = record.get('attack_id', 'N/A')

        # Skip if we already processed this prefix in this run
        if prefix in processed_prefixes:
            logger.info(f"Prefix {prefix} already processed in this run - marking as success")
            mark_withdrawn(record['id'], success=True, method='auto_scheduled')
            success_count += 1
            # Don't add to results again - avoid duplicate in notification
            continue

        logger.info(f"Processing withdrawal for {prefix} (Attack: {attack_id})")

        # Attempt withdrawal
        success, error, already_withdrawn = withdraw_prefix(prefix, config, prefix_mapping)

        if success:
            if already_withdrawn:
                logger.info(f"Prefix {prefix} was already withdrawn")
            else:
                logger.info(f"Successfully withdrew {prefix}")
            mark_withdrawn(record['id'], success=True, method='auto_scheduled')
            success_count += 1
            results.append((prefix, True, None))
            processed_prefixes.add(prefix)
        else:
            logger.error(f"Failed to withdraw {prefix}: {error}")
            mark_withdrawn(record['id'], success=False, error=error, method='auto_scheduled')
            fail_count += 1
            results.append((prefix, False, error))
            processed_prefixes.add(prefix)

    # Send summary notification
    if results:
        send_summary_notification(results, config)

    logger.info(f"Completed: {success_count} successful, {fail_count} failed")

    return 0 if fail_count == 0 else 1


def send_summary_notification(results, config):
    """Send Telegram notification for withdrawal results."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    success_list = [r for r in results if r[1]]
    fail_list = [r for r in results if not r[1]]

    if len(results) == 1:
        # Single prefix - detailed notification
        prefix, success, error = results[0]

        if success:
            message = f"""🛡️ *CLOUDFLARE DDoS PROTECTION*

🔚 *SCHEDULED BGP WITHDRAWAL*

✅ *Status:* PREFIX WITHDRAWN
🎯 *Method:* Auto-scheduled (15min constraint)

📡 *PREFIX INFO*
📍 *CIDR:* `{prefix}`

⏱️ *TIMING*
🕐 *Withdrawn at:* {now}
⏳ *BGP Withdrawal:* ~15 minutes

🔄 *BGP STATUS*
🔙 Traffic returning to origin path
⚠️ Direct routing resumed
📊 Magic Transit protection disabled

🤖 *Operator:* Scheduled Task (Auto)

🏢 *GOLINE SOC* | _Magic Transit On-Demand_"""
        else:
            message = f"""🛡️ *CLOUDFLARE DDoS PROTECTION*

❌ *SCHEDULED WITHDRAWAL FAILED*

❌ *Status:* WITHDRAWAL FAILED
🎯 *Method:* Auto-scheduled

📡 *PREFIX INFO*
📍 *CIDR:* `{prefix}`

❌ *ERROR*
`{error}`

⚠️ *Action Required:* Manual intervention needed

🤖 *Operator:* Scheduled Task (Auto)

🏢 *GOLINE SOC* | _Magic Transit On-Demand_"""

    else:
        # Multiple prefixes - summary notification
        message = f"""🛡️ *CLOUDFLARE DDoS PROTECTION*

🔚 *BULK SCHEDULED WITHDRAWAL*

🎯 *Method:* Auto-scheduled (15min constraint)
⏱️ *Time:* {now}

📊 *SUMMARY*
📦 *Total:* {len(results)}
✅ *Withdrawn:* {len(success_list)}
❌ *Failed:* {len(fail_list)}"""

        if success_list:
            message += "\n\n✅ *Successful:*"
            for prefix, _, _ in success_list:
                message += f"\n  • `{prefix}`"

        if fail_list:
            message += "\n\n❌ *Failed:*"
            for prefix, _, error in fail_list:
                message += f"\n  • `{prefix}`: {error}"

        message += f"""

🤖 *Operator:* Scheduled Task (Auto)

🏢 *GOLINE SOC* | _Magic Transit On-Demand_"""

    send_telegram_notification(message, config)


def show_status():
    """Show current status of pending withdrawals."""
    init_database()

    print("\n" + "=" * 85)
    print("PENDING WITHDRAWALS STATUS")
    print("=" * 85)

    pending = get_all_pending()
    failed = get_failed_withdrawals()

    if not pending and not failed:
        print("\nNo pending or failed withdrawals.\n")
    else:
        if pending:
            print(f"\n{'Prefix':<20} {'Attack ID':<15} {'Withdraw After':<22} {'Status':<10} {'Ready':<10}")
            print("-" * 85)

            now = datetime.now(timezone.utc)

            for record in pending:
                prefix = record['prefix']
                attack_id = (record.get('attack_id') or 'N/A')[:12]
                withdraw_after = record['withdraw_after']
                status = record['status']

                # Check if ready
                try:
                    wa_time = datetime.fromisoformat(withdraw_after.replace('Z', '+00:00'))
                    if wa_time.tzinfo is None:
                        wa_time = wa_time.replace(tzinfo=timezone.utc)
                    if now >= wa_time:
                        ready = "READY"
                    else:
                        remaining = (wa_time - now).total_seconds()
                        mins = int(remaining // 60)
                        secs = int(remaining % 60)
                        ready = f"in {mins}m {secs}s"
                except:
                    ready = "?"

                print(f"{prefix:<20} {attack_id:<15} {withdraw_after:<22} {status:<10} {ready:<10}")

        if failed:
            print(f"\n⚠️  FAILED WITHDRAWALS (use --failed for details): {len(failed)}")

    # Show stats
    stats = get_stats()
    print("\n" + "-" * 70)
    print(f"Pending: {stats['pending_withdrawals']} | "
          f"Total Withdrawals: {stats['total_withdrawals']} | "
          f"Success: {stats['successful_withdrawals']} | "
          f"Events Today: {stats['events_today']}")
    print("=" * 70 + "\n")


def show_history(limit=20):
    """Show withdrawal history."""
    init_database()

    print("\n" + "=" * 80)
    print("WITHDRAWAL HISTORY")
    print("=" * 80)

    history = get_attack_history(limit)

    if not history:
        print("\nNo withdrawal history.\n")
    else:
        print(f"\n{'Withdrawn At':<22} {'Prefix':<20} {'Method':<12} {'Duration':<12} {'Status':<8}")
        print("-" * 80)

        for record in history:
            withdrawn_at = (record.get('withdrawn_at') or 'N/A')[:19]
            prefix = record['prefix']
            method = (record.get('withdraw_method') or 'N/A')[:10]
            duration = format_duration(record.get('protection_duration_seconds'))
            status = record.get('status', 'N/A')

            status_icon = "✅" if status == 'success' else "❌"

            print(f"{withdrawn_at:<22} {prefix:<20} {method:<12} {duration:<12} {status_icon} {status:<6}")

    print("=" * 80 + "\n")


def show_failed():
    """Show failed withdrawals awaiting retry."""
    init_database()

    print("\n" + "=" * 90)
    print("FAILED WITHDRAWALS (Awaiting Retry)")
    print("=" * 90)

    failed = get_failed_withdrawals()

    if not failed:
        print("\nNo failed withdrawals.\n")
    else:
        print(f"\n{'ID':<5} {'Prefix':<20} {'Retry#':<7} {'Next Retry':<22} {'Last Error':<30}")
        print("-" * 90)

        for record in failed:
            rec_id = record['id']
            prefix = record['prefix']
            retry_count = record.get('retry_count', 0)
            max_retries = record.get('max_retries', 5) or 5
            next_retry = (record.get('next_retry_at') or 'N/A')[:19]
            last_error = (record.get('last_error') or 'N/A')[:28]

            print(f"{rec_id:<5} {prefix:<20} {retry_count}/{max_retries:<5} {next_retry:<22} {last_error:<30}")

    print("=" * 90)
    print("\nTo reset a failed withdrawal for immediate retry:")
    print("  python3 -c \"from db_manager import reset_failed_for_retry; reset_failed_for_retry(<ID>)\"")
    print("=" * 90 + "\n")


def run_cleanup(max_age_hours=24):
    """Run manual cleanup of stale pending withdrawals."""
    init_database()

    print(f"\nCleaning up pending withdrawals older than {max_age_hours} hours...")
    cleaned = cleanup_stale_pending(max_age_hours=max_age_hours)
    print(f"Cleaned up {cleaned} stale record(s).\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Check and process pending BGP prefix withdrawals'
    )
    parser.add_argument('--status', action='store_true',
                       help='Show current status of pending withdrawals')
    parser.add_argument('--history', action='store_true',
                       help='Show withdrawal history')
    parser.add_argument('--failed', action='store_true',
                       help='Show failed withdrawals awaiting retry')
    parser.add_argument('--cleanup', action='store_true',
                       help='Manual cleanup of stale pending withdrawals')
    parser.add_argument('--cleanup-hours', type=int, default=24,
                       help='Max age in hours for cleanup (default: 24)')
    parser.add_argument('--limit', type=int, default=20,
                       help='Limit for history (default: 20)')

    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if args.history:
        show_history(args.limit)
        return 0

    if args.failed:
        show_failed()
        return 0

    if args.cleanup:
        return run_cleanup(args.cleanup_hours)

    # Default: process pending withdrawals
    return process_pending_withdrawals()


if __name__ == '__main__':
    sys.exit(main())
