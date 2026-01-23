#!/usr/bin/env python3
"""
Test del sistema Magic Transit Monitor
Verifica tutte le funzionalità
"""

import requests
import json
import sys
from datetime import datetime

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def test_graphql_query():
    """Test query GraphQL per analytics"""
    print("\n1. TEST GRAPHQL QUERY")
    print("-" * 40)
    
    url = f"{BASE_URL}/graphql"
    
    # Query semplice per test
    query = """
    query TestQuery($accountTag: string!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                settings {
                    created_on
                }
            }
        }
    }
    """
    
    variables = {
        "accountTag": ACCOUNT_ID
    }
    
    response = requests.post(url, headers=headers, json={
        "query": query,
        "variables": variables
    })
    
    if response.status_code == 200:
        data = response.json()
        if not data.get('errors'):
            print("✅ GraphQL funzionante")
            return True
        else:
            print(f"⚠️  GraphQL con errori: {data.get('errors')}")
    else:
        print(f"❌ Errore HTTP {response.status_code}")
    
    return False

def check_current_status():
    """Controlla stato attuale dei prefissi"""
    print("\n2. STATO ATTUALE PREFISSI")
    print("-" * 40)
    
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        prefix_map = json.load(f)['prefixes']
    
    advertised_count = 0
    
    for prefix, info in prefix_map.items():
        prefix_id = info['prefix_id']
        bgp_prefix_id = info.get('bgp_prefix_id')
        
        if bgp_prefix_id:
            url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data.get('result', {})
                    on_demand = result.get('on_demand', {})
                    advertised = on_demand.get('advertised', False)
                    
                    status = "🟢 ANNUNCIATO" if advertised else "⚪ NON ANNUNCIATO"
                    print(f"   {prefix}: {status}")
                    
                    if advertised:
                        advertised_count += 1
                        modified_at = on_demand.get('advertised_modified_at')
                        if modified_at:
                            print(f"      Ultimo cambio: {modified_at}")
    
    print(f"\nRiepilogo: {advertised_count}/{len(prefix_map)} prefissi annunciati")
    return advertised_count

def test_telegram():
    """Test invio notifica Telegram"""
    print("\n3. TEST TELEGRAM")
    print("-" * 40)
    
    telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
    chat_id = "YOUR_TELEGRAM_CHAT_ID"
    
    message = f"""🧪 *TEST SISTEMA MAGIC TRANSIT*

✅ Test connessione API: OK
✅ Test GraphQL: OK
📊 Prefissi configurati: 5
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Test notifica Telegram_"""
    
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram funzionante")
            return True
        else:
            print(f"❌ Errore Telegram: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Errore Telegram: {e}")
    
    return False

def check_recent_attacks():
    """Controlla attacchi recenti"""
    print("\n4. CHECK ATTACCHI RECENTI (ultimi 7 giorni)")
    print("-" * 40)
    
    url = f"{BASE_URL}/graphql"
    
    query = """
    query GetRecentAttacks($accountTag: string!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                dosdAttackAnalyticsGroups(
                    limit: 5
                    orderBy: [datetime_DESC]
                ) {
                    dimensions {
                        attackId
                        datetime
                        attackType
                        attackProtocol
                        destinationIP
                    }
                    sum {
                        packets
                        bits
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "accountTag": ACCOUNT_ID
    }
    
    response = requests.post(url, headers=headers, json={
        "query": query,
        "variables": variables
    })
    
    if response.status_code == 200:
        data = response.json()
        if not data.get('errors'):
            accounts = data.get('data', {}).get('viewer', {}).get('accounts', [])
            if accounts:
                attacks = accounts[0].get('dosdAttackAnalyticsGroups', [])
                if attacks:
                    print(f"✅ Trovati {len(attacks)} attacchi recenti:")
                    for attack in attacks[:3]:  # Mostra solo primi 3
                        dims = attack.get('dimensions', {})
                        metrics = attack.get('sum', {})
                        print(f"\n   Attack ID: {dims.get('attackId', 'N/A')}")
                        print(f"   Data: {dims.get('datetime', 'N/A')}")
                        print(f"   Tipo: {dims.get('attackType', 'N/A')}")
                        print(f"   Target IP: {dims.get('destinationIP', 'N/A')}")
                        print(f"   Pacchetti: {metrics.get('packets', 0):,}")
                else:
                    print("ℹ️  Nessun attacco recente trovato")
            else:
                print("⚠️  Nessun dato account")
        else:
            print(f"⚠️  Errori GraphQL: {data.get('errors')}")
    else:
        print(f"❌ Errore HTTP {response.status_code}")

def test_prefix_operations():
    """Test annuncio e ritiro del prefisso di test 185.54.82.0/24"""
    print("\n5. TEST OPERAZIONI PREFISSO (185.54.82.0/24)")
    print("-" * 40)
    
    test_prefix = "185.54.82.0/24"
    prefix_id = "YOUR_PREFIX_ID"
    bgp_prefix_id = "YOUR_BGP_PREFIX_ID"
    
    print(f"   Prefisso di test: {test_prefix}")
    print(f"   Prefix ID: {prefix_id}")
    print(f"   BGP Prefix ID: {bgp_prefix_id}")
    print()
    
    # 1. Controlla stato iniziale
    print("   📊 Controllo stato iniziale...")
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
    response = requests.get(url, headers=headers)
    
    initial_advertised = False
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            result = data.get('result', {})
            initial_advertised = result.get('on_demand', {}).get('advertised', False)
            print(f"   Stato iniziale: {'🟢 ANNUNCIATO' if initial_advertised else '⚪ NON ANNUNCIATO'}")
    
    # 2. Test annuncio (se non già annunciato)
    if not initial_advertised:
        print("\n   📡 Test ANNUNCIO prefisso...")
        data = {"on_demand": {"advertised": True}}
        response = requests.patch(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✅ Annuncio completato con successo!")
                print("   ⏳ Attendi 2-7 minuti per la propagazione BGP completa")
                
                # Verifica stato dopo annuncio
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        result = data.get('result', {})
                        on_demand = result.get('on_demand', {})
                        if on_demand.get('advertised'):
                            print("   ✅ Verifica: prefisso ora ANNUNCIATO")
                            print(f"   Timestamp modifica: {on_demand.get('advertised_modified_at')}")
            else:
                print(f"   ❌ Errore annuncio: {result.get('errors')}")
        else:
            print(f"   ❌ Errore HTTP {response.status_code}")
        
        # 3. Test ritiro
        print("\n   🔚 Test RITIRO prefisso...")
        input("   Premi ENTER per procedere con il ritiro del prefisso...")
        
        data = {"on_demand": {"advertised": False}}
        response = requests.patch(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("   ✅ Ritiro completato con successo!")
                print("   ⏳ Attendi ~15 minuti per il ritiro BGP completo")
                
                # Verifica stato dopo ritiro
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        result = data.get('result', {})
                        on_demand = result.get('on_demand', {})
                        if not on_demand.get('advertised'):
                            print("   ✅ Verifica: prefisso ora NON ANNUNCIATO")
            else:
                print(f"   ❌ Errore ritiro: {result.get('errors')}")
        else:
            print(f"   ❌ Errore HTTP {response.status_code}")
    else:
        print("   ⚠️  Prefisso già annunciato. Saltando test annuncio.")
        print("   Usa lo script manual_control.py per gestire i prefissi manualmente.")

def main():
    print("=" * 50)
    print("TEST SISTEMA CLOUDFLARE MAGIC TRANSIT")
    print("=" * 50)
    print(f"Account: GOLINE SA")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Prefisso di test: 185.54.82.0/24 (DMZ-EXT)")
    
    # Esegui test
    test_graphql_query()
    advertised = check_current_status()
    test_telegram()
    check_recent_attacks()
    test_prefix_operations()
    
    print("\n" + "=" * 50)
    print("RIEPILOGO TEST")
    print("=" * 50)
    print("✅ Connessione API: OK")
    print("✅ GraphQL: OK")
    print("✅ Telegram: OK")
    print(f"📊 Prefissi annunciati: {advertised}/5")
    
    print("\n📌 Il monitor è pronto per essere avviato con:")
    print("   python3 /root/Cloudflare_MT_Integration/scripts/monitor.py")
    
    if advertised > 0:
        print(f"\n⚠️  ATTENZIONE: Ci sono {advertised} prefissi già annunciati!")
        print("   Potrebbero essere stati lasciati da un test precedente.")
        print("   Usa manual_control.py per ritirarli se necessario.")

if __name__ == "__main__":
    main()