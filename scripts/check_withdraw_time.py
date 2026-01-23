#!/usr/bin/env python3
"""
Check Withdraw Time - Verifica quando un prefisso può essere ritirato

Uso:
    python3 check_withdraw_time.py                    # Tutti i prefissi
    python3 check_withdraw_time.py 185.54.83.0/24    # Prefisso specifico
    python3 check_withdraw_time.py --help            # Aiuto
"""

import requests
import json
import sys
from datetime import datetime, timedelta, timezone

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

# Vincolo Cloudflare: 15 minuti minimo tra annuncio e ritiro
WITHDRAW_DELAY_MINUTES = 15

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def load_prefix_mapping():
    """Carica la mappatura dei prefissi"""
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        return json.load(f)['prefixes']

def get_prefix_status(prefix_id, bgp_prefix_id):
    """Ottiene lo stato di un prefisso BGP"""
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return data.get('result', {})
    return None

def calculate_withdraw_time(advertised_modified_at):
    """Calcola quando è possibile ritirare il prefisso"""
    if not advertised_modified_at:
        return None, None, None

    mod_time = datetime.fromisoformat(advertised_modified_at.replace('Z', '+00:00'))
    withdraw_time = mod_time + timedelta(minutes=WITHDRAW_DELAY_MINUTES)
    now = datetime.now(timezone.utc)

    can_withdraw = now >= withdraw_time

    if can_withdraw:
        remaining = None
    else:
        remaining = withdraw_time - now

    return withdraw_time, can_withdraw, remaining

def print_prefix_status(prefix, info, result):
    """Stampa lo stato di un prefisso con calcolo withdraw time"""
    on_demand = result.get('on_demand', {})
    advertised = on_demand.get('advertised', False)
    modified_at = on_demand.get('advertised_modified_at')
    locked = on_demand.get('locked', False)

    print(f"\n{'='*60}")
    print(f"PREFISSO: {prefix}")
    print(f"Descrizione: {info.get('description', 'N/A')}")
    print(f"{'='*60}")

    # Stato lock
    if locked:
        print(f"🔒 LOCKED: Prefisso bloccato, non modificabile")

    # Stato annuncio
    if advertised:
        print(f"📡 STATO: 🟢 ANNUNCIATO")
    else:
        print(f"📡 STATO: ⚪ NON ANNUNCIATO")

    # Timestamp modifica
    print(f"📅 advertised_modified_at: {modified_at or 'N/A'}")

    # Calcolo withdraw time (solo se annunciato)
    if advertised and modified_at:
        withdraw_time, can_withdraw, remaining = calculate_withdraw_time(modified_at)

        print(f"\n--- CALCOLO WITHDRAW ---")
        print(f"Annunciato alle:     {datetime.fromisoformat(modified_at.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"Withdraw possibile:  {withdraw_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"Ora attuale:         {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

        if can_withdraw:
            print(f"\n✅ WITHDRAW POSSIBILE ORA")
        else:
            mins = remaining.seconds // 60
            secs = remaining.seconds % 60
            print(f"\n⏳ WITHDRAW TRA: {mins} minuti e {secs} secondi")
    elif not advertised:
        print(f"\nℹ️  Prefisso non annunciato - nessun vincolo di withdraw")

def check_all_prefixes():
    """Controlla lo stato di tutti i prefissi"""
    prefix_map = load_prefix_mapping()

    print("\n" + "="*60)
    print("CHECK WITHDRAW TIME - TUTTI I PREFISSI")
    print("="*60)
    print(f"Ora attuale: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Vincolo Cloudflare: {WITHDRAW_DELAY_MINUTES} minuti tra annuncio e ritiro")

    advertised_count = 0

    for prefix, info in prefix_map.items():
        bgp_prefix_id = info.get('bgp_prefix_id')

        if bgp_prefix_id:
            result = get_prefix_status(info['prefix_id'], bgp_prefix_id)
            if result:
                print_prefix_status(prefix, info, result)
                if result.get('on_demand', {}).get('advertised'):
                    advertised_count += 1
        else:
            print(f"\n⚠️  {prefix}: No BGP prefix ID configurato")

    # Riepilogo
    print(f"\n{'='*60}")
    print(f"RIEPILOGO: {advertised_count}/{len(prefix_map)} prefissi annunciati")
    print(f"{'='*60}")

def check_single_prefix(target_prefix):
    """Controlla lo stato di un singolo prefisso"""
    prefix_map = load_prefix_mapping()

    if target_prefix not in prefix_map:
        print(f"❌ Prefisso {target_prefix} non trovato nel mapping")
        print(f"Prefissi disponibili: {', '.join(prefix_map.keys())}")
        return

    info = prefix_map[target_prefix]
    bgp_prefix_id = info.get('bgp_prefix_id')

    if not bgp_prefix_id:
        print(f"⚠️  {target_prefix}: No BGP prefix ID configurato")
        return

    result = get_prefix_status(info['prefix_id'], bgp_prefix_id)
    if result:
        print_prefix_status(target_prefix, info, result)
    else:
        print(f"❌ Errore nel recupero dello stato per {target_prefix}")

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ['--help', '-h', 'help']:
            print(__doc__)
            print("\nPrefissi disponibili:")
            prefix_map = load_prefix_mapping()
            for prefix, info in prefix_map.items():
                print(f"  - {prefix} ({info.get('description', 'N/A')})")
        else:
            # Assume it's a prefix CIDR
            check_single_prefix(arg)
    else:
        check_all_prefixes()

if __name__ == "__main__":
    main()
