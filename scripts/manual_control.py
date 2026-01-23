#!/usr/bin/env python3
"""
Controllo Manuale Prefissi BGP
Script per gestire manualmente l'annuncio e il ritiro dei prefissi
"""

import requests
import json
import sys
from datetime import datetime, timedelta, timezone

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

# Prefisso di test predefinito: 185.54.82.0/24 (DMZ-EXT)
TEST_PREFIX = "185.54.82.0/24"
TEST_PREFIX_ID = "YOUR_PREFIX_ID"
TEST_BGP_PREFIX_ID = "YOUR_BGP_PREFIX_ID"

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
            result = data.get('result', {})
            on_demand = result.get('on_demand', {})
            return {
                'advertised': on_demand.get('advertised', False),
                'modified_at': on_demand.get('advertised_modified_at'),
                'full_data': result
            }
    return None

def check_advertise_constraint(modified_at):
    """Check if the 15-minute constraint is satisfied for RE-ADVERTISE after withdrawal

    Returns:
        tuple: (can_advertise, remaining_seconds, advertise_time_str)
    """
    if not modified_at:
        return True, 0, None

    try:
        mod_time = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
        advertise_time = mod_time + timedelta(minutes=15)
        now = datetime.now(timezone.utc)

        if now >= advertise_time:
            return True, 0, None
        else:
            remaining = (advertise_time - now).total_seconds()
            # Format advertise time in local timezone (UTC+1 for Switzerland)
            advertise_time_local = advertise_time + timedelta(hours=1)
            advertise_time_str = advertise_time_local.strftime('%H:%M:%S')
            return False, remaining, advertise_time_str
    except:
        return True, 0, None

def advertise_prefix(prefix_id, bgp_prefix_id, prefix_name):
    """Annuncia un prefisso BGP"""
    print(f"\n📡 ANNUNCIO prefisso {prefix_name}...")
    print("-" * 40)

    # Check current status and 15-minute constraint
    status = get_prefix_status(prefix_id, bgp_prefix_id)
    if status and not status['advertised']:
        can_advertise, remaining, advertise_time = check_advertise_constraint(status['modified_at'])
        if not can_advertise:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            print(f"❌ ERRORE: Non è possibile annunciare {prefix_name}")
            print(f"   Cloudflare richiede 15 minuti tra ritiro e ri-annuncio")
            print(f"   Annuncio disponibile alle {advertise_time} (tra {mins}m {secs}s)")
            return False

    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
    data = {"on_demand": {"advertised": True}}

    response = requests.patch(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print(f"✅ Prefisso {prefix_name} ANNUNCIATO con successo!")
            print("⏳ La propagazione BGP completa richiede 2-7 minuti")
            
            # Verifica stato
            status = get_prefix_status(prefix_id, bgp_prefix_id)
            if status and status['advertised']:
                print(f"📊 Stato verificato: ANNUNCIATO")
                if status['modified_at']:
                    print(f"⏰ Timestamp modifica: {status['modified_at']}")
            
            # Notifica Telegram
            send_telegram_notification(
                f"📡 *PREFISSO ANNUNCIATO MANUALMENTE*\n\n"
                f"Prefisso: `{prefix_name}`\n"
                f"Operatore: Controllo Manuale\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return True
        else:
            print(f"❌ Errore: {result.get('errors')}")
    else:
        print(f"❌ Errore HTTP {response.status_code}")
    
    return False

def withdraw_prefix(prefix_id, bgp_prefix_id, prefix_name):
    """Ritira un prefisso BGP"""
    print(f"\n🔚 RITIRO prefisso {prefix_name}...")
    print("-" * 40)
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
    data = {"on_demand": {"advertised": False}}
    
    response = requests.patch(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print(f"✅ Prefisso {prefix_name} RITIRATO con successo!")
            print("⏳ Il ritiro BGP completo richiede ~15 minuti")
            
            # Verifica stato
            status = get_prefix_status(prefix_id, bgp_prefix_id)
            if status and not status['advertised']:
                print(f"📊 Stato verificato: NON ANNUNCIATO")
            
            # Notifica Telegram
            send_telegram_notification(
                f"🔚 *PREFISSO RITIRATO MANUALMENTE*\n\n"
                f"Prefisso: `{prefix_name}`\n"
                f"Operatore: Controllo Manuale\n"
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return True
        else:
            print(f"❌ Errore: {result.get('errors')}")
    else:
        print(f"❌ Errore HTTP {response.status_code}")
    
    return False

def send_telegram_notification(message):
    """Invia notifica Telegram"""
    telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
    chat_id = "YOUR_TELEGRAM_CHAT_ID"
    
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        requests.post(url, json=data, timeout=10)
    except:
        pass  # Ignora errori Telegram

def show_all_status():
    """Mostra lo stato di tutti i prefissi"""
    print("\n📊 STATO DI TUTTI I PREFISSI")
    print("=" * 60)
    
    prefix_map = load_prefix_mapping()
    advertised_count = 0
    
    for prefix, info in prefix_map.items():
        prefix_id = info['prefix_id']
        bgp_prefix_id = info.get('bgp_prefix_id')
        description = info.get('description', 'N/A')
        
        if bgp_prefix_id:
            status = get_prefix_status(prefix_id, bgp_prefix_id)
            if status:
                if status['advertised']:
                    advertised_count += 1
                    status_icon = "🟢"
                    status_text = "ANNUNCIATO"
                else:
                    status_icon = "⚪"
                    status_text = "NON ANNUNCIATO"
                
                print(f"{status_icon} {prefix:20} {status_text:15} {description}")
                
                if status['advertised'] and status['modified_at']:
                    print(f"   └─ Ultimo cambio: {status['modified_at']}")
        else:
            print(f"❌ {prefix:20} NO BGP PREFIX   {description}")
    
    print("=" * 60)
    print(f"Totale: {advertised_count}/{len(prefix_map)} prefissi annunciati")
    
    if advertised_count > 0:
        print(f"\n⚠️  ATTENZIONE: Ci sono {advertised_count} prefissi attualmente annunciati")

def interactive_menu():
    """Menu interattivo per controllo manuale"""
    while True:
        print("\n" + "=" * 60)
        print("CONTROLLO MANUALE PREFISSI MAGIC TRANSIT")
        print("=" * 60)
        print(f"Prefisso di test predefinito: {TEST_PREFIX}")
        print("-" * 60)
        print("1. Mostra stato di tutti i prefissi")
        print("2. Annuncia prefisso di test (185.54.82.0/24)")
        print("3. Ritira prefisso di test (185.54.82.0/24)")
        print("4. Annuncia TUTTI i prefissi")
        print("5. Ritira TUTTI i prefissi")
        print("6. Stato dettagliato prefisso di test")
        print("0. Esci")
        print("-" * 60)
        
        choice = input("Seleziona opzione: ").strip()
        
        if choice == "1":
            show_all_status()
            
        elif choice == "2":
            status = get_prefix_status(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID)
            if status and status['advertised']:
                print(f"\n⚠️  Il prefisso {TEST_PREFIX} è già annunciato!")
                confirm = input("Vuoi procedere comunque? (s/n): ").lower()
                if confirm != 's':
                    continue
            advertise_prefix(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID, TEST_PREFIX)
            
        elif choice == "3":
            status = get_prefix_status(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID)
            if status and not status['advertised']:
                print(f"\n⚠️  Il prefisso {TEST_PREFIX} non è annunciato!")
                confirm = input("Vuoi procedere comunque? (s/n): ").lower()
                if confirm != 's':
                    continue
            withdraw_prefix(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID, TEST_PREFIX)
            
        elif choice == "4":
            print("\n⚠️  ATTENZIONE: Stai per annunciare TUTTI i prefissi!")
            confirm = input("Sei sicuro? (digita 'CONFERMA'): ")
            if confirm == "CONFERMA":
                prefix_map = load_prefix_mapping()
                for prefix, info in prefix_map.items():
                    if info.get('bgp_prefix_id'):
                        advertise_prefix(info['prefix_id'], info['bgp_prefix_id'], prefix)
            
        elif choice == "5":
            print("\n⚠️  ATTENZIONE: Stai per ritirare TUTTI i prefissi!")
            confirm = input("Sei sicuro? (digita 'CONFERMA'): ")
            if confirm == "CONFERMA":
                prefix_map = load_prefix_mapping()
                for prefix, info in prefix_map.items():
                    if info.get('bgp_prefix_id'):
                        withdraw_prefix(info['prefix_id'], info['bgp_prefix_id'], prefix)
            
        elif choice == "6":
            print(f"\n📊 STATO DETTAGLIATO: {TEST_PREFIX}")
            print("-" * 40)
            status = get_prefix_status(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID)
            if status:
                print(f"Annunciato: {'Sì' if status['advertised'] else 'No'}")
                print(f"Ultimo cambio: {status['modified_at'] or 'N/A'}")
                print("\nDati completi:")
                print(json.dumps(status['full_data'], indent=2))
            
        elif choice == "0":
            print("\n👋 Uscita...")
            break
        
        else:
            print("\n❌ Opzione non valida")

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            show_all_status()
        elif command == "advertise-test":
            advertise_prefix(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID, TEST_PREFIX)
        elif command == "withdraw-test":
            withdraw_prefix(TEST_PREFIX_ID, TEST_BGP_PREFIX_ID, TEST_PREFIX)
        elif command == "help":
            print("Uso:")
            print("  python3 manual_control.py           # Menu interattivo")
            print("  python3 manual_control.py status    # Mostra stato prefissi")
            print("  python3 manual_control.py advertise-test  # Annuncia 185.54.82.0/24")
            print("  python3 manual_control.py withdraw-test   # Ritira 185.54.82.0/24")
        else:
            print(f"Comando non riconosciuto: {command}")
            print("Usa 'python3 manual_control.py help' per aiuto")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()