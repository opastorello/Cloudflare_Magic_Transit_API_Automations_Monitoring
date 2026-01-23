#!/usr/bin/env python3
"""
Script migliorato per verificare attacchi DDoS in corso
Utilizza le API corrette per Magic Transit
"""

import requests
import json
from datetime import datetime, timedelta, timezone
import sys

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def check_magic_transit_analytics(minutes_back=5):
    """
    Controlla Magic Transit Network Analytics
    """
    print(f"\n📊 MAGIC TRANSIT ANALYTICS (ultimi {minutes_back} minuti)")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    start_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Query per Magic Transit Network Analytics
    query = """
    query GetMagicTransitAnalytics($accountTag: string!, $datetimeStart: Time!, $datetimeEnd: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                magicTransitNetworkAnalyticsAdaptiveGroups(
                    filter: {
                        datetime_geq: $datetimeStart
                        datetime_leq: $datetimeEnd
                    }
                    orderBy: [sum_packets_DESC]
                    limit: 20
                ) {
                    dimensions {
                        datetime
                        coloCity
                        coloCountry
                        ipDestinationAddress
                        ipSourceAddress
                        ipProtocol
                        outcome
                        ruleset
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
        "accountTag": ACCOUNT_ID,
        "datetimeStart": start_time,
        "datetimeEnd": end_time
    }
    
    try:
        response = requests.post(url, headers=headers, json={
            "query": query,
            "variables": variables
        }, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if not data.get('errors'):
                accounts = data.get('data', {}).get('viewer', {}).get('accounts', [])
                if accounts and len(accounts) > 0:
                    analytics = accounts[0].get('magicTransitNetworkAnalyticsAdaptiveGroups', [])
                    
                    if analytics:
                        print(f"✅ Trovati {len(analytics)} eventi:\n")
                        
                        dropped_traffic = []
                        passed_traffic = []
                        
                        for event in analytics:
                            dims = event.get('dimensions', {})
                            metrics = event.get('sum', {})
                            outcome = dims.get('outcome', '')
                            
                            if outcome == 'drop':
                                dropped_traffic.append(event)
                            else:
                                passed_traffic.append(event)
                        
                        if dropped_traffic:
                            print(f"🚨 TRAFFICO BLOCCATO (possibile attacco):")
                            for event in dropped_traffic[:5]:
                                dims = event.get('dimensions', {})
                                metrics = event.get('sum', {})
                                print(f"   Destinazione: {dims.get('ipDestinationAddress', 'N/A')}")
                                print(f"   Sorgente: {dims.get('ipSourceAddress', 'N/A')}")
                                print(f"   Pacchetti: {metrics.get('packets', 0):,}")
                                print(f"   Protocollo: {dims.get('ipProtocol', 'N/A')}")
                                print(f"   Timestamp: {dims.get('datetime', 'N/A')}")
                                print()
                        
                        if not dropped_traffic:
                            print("✅ Nessun traffico bloccato (nessun attacco rilevato)")
                    else:
                        print("ℹ️  Nessun evento nel periodo specificato")
                else:
                    print("ℹ️  Nessun dato account disponibile")
            else:
                # Proviamo query alternativa
                print("ℹ️  Query non supportata, provo alternativa...")
                return try_alternative_query(minutes_back)
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
    
    return False

def try_alternative_query(minutes_back=5):
    """
    Query alternativa per rilevare attacchi
    """
    print("\n🔄 QUERY ALTERNATIVA")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    start_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Query semplificata per eventi DDoS
    query = """
    query GetDDoSEvents($accountTag: string!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                dosdAttackAnalyticsGroups(
                    limit: 10
                    orderBy: [datetime_DESC]
                ) {
                    dimensions {
                        attackId
                        datetime
                        attackType
                        attackProtocol
                        destinationIP
                        action
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
    
    try:
        response = requests.post(url, headers=headers, json={
            "query": query,
            "variables": variables
        }, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if not data.get('errors'):
                accounts = data.get('data', {}).get('viewer', {}).get('accounts', [])
                if accounts and len(accounts) > 0:
                    attacks = accounts[0].get('dosdAttackAnalyticsGroups', [])
                    
                    if attacks:
                        print(f"📝 Ultimi {len(attacks)} eventi DDoS:\n")
                        
                        recent_attacks = []
                        now = datetime.now(timezone.utc)
                        
                        for attack in attacks:
                            dims = attack.get('dimensions', {})
                            attack_time_str = dims.get('datetime', '')
                            
                            # Controlla se l'attacco è recente (ultimi X minuti)
                            if attack_time_str:
                                try:
                                    attack_time = datetime.fromisoformat(attack_time_str.replace('Z', '+00:00'))
                                    time_diff = (now - attack_time).total_seconds() / 60
                                    
                                    if time_diff <= minutes_back:
                                        recent_attacks.append(attack)
                                except:
                                    pass
                        
                        if recent_attacks:
                            print(f"🚨 ATTACCHI NEGLI ULTIMI {minutes_back} MINUTI:")
                            for attack in recent_attacks:
                                dims = attack.get('dimensions', {})
                                metrics = attack.get('sum', {})
                                print(f"   ID Attacco: {dims.get('attackId', 'N/A')}")
                                print(f"   Tipo: {dims.get('attackType', 'N/A')}")
                                print(f"   Target: {dims.get('destinationIP', 'N/A')}")
                                print(f"   Pacchetti: {metrics.get('packets', 0):,}")
                                print(f"   Timestamp: {dims.get('datetime', 'N/A')}")
                                print()
                            return True
                        else:
                            print(f"✅ Nessun attacco negli ultimi {minutes_back} minuti")
                            if attacks:
                                last_attack = attacks[0]
                                dims = last_attack.get('dimensions', {})
                                print(f"\nUltimo attacco registrato:")
                                print(f"   Timestamp: {dims.get('datetime', 'N/A')}")
                                print(f"   Target: {dims.get('destinationIP', 'N/A')}")
                    else:
                        print("✅ Nessun evento DDoS registrato")
                else:
                    print("ℹ️  Nessun dato disponibile")
            else:
                print(f"⚠️  Errori: {data.get('errors')}")
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
    
    return False

def check_prefix_status():
    """
    Controlla lo stato dei prefissi e se sono sotto attacco
    """
    print("\n📡 STATO PREFISSI E RILEVAMENTO ATTACCHI")
    print("-" * 60)
    
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        prefix_map = json.load(f)['prefixes']
    
    print("Prefissi monitorati:")
    for prefix, info in prefix_map.items():
        print(f"  • {prefix} ({info.get('description', 'N/A')})")
    print()
    
    # Verifica stato annuncio per ogni prefisso
    advertised_count = 0
    for prefix, info in prefix_map.items():
        if info.get('bgp_prefix_id'):
            prefix_id = info['prefix_id']
            bgp_prefix_id = info['bgp_prefix_id']
            
            url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data.get('result', {})
                    on_demand = result.get('on_demand', {})
                    advertised = on_demand.get('advertised', False)
                    
                    if advertised:
                        advertised_count += 1
                        modified_at = on_demand.get('advertised_modified_at', 'N/A')
                        print(f"🟢 {prefix}: ANNUNCIATO")
                        print(f"   └─ Attivato: {modified_at}")
                        
                        # Calcola da quanto tempo è annunciato
                        if modified_at and modified_at != 'N/A':
                            try:
                                announce_time = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
                                elapsed = datetime.now(timezone.utc) - announce_time
                                minutes = int(elapsed.total_seconds() / 60)
                                print(f"   └─ Durata: {minutes} minuti")
                                
                                if minutes >= 15:
                                    print(f"   └─ ✅ Può essere ritirato (>15 min)")
                                else:
                                    remaining = 15 - minutes
                                    print(f"   └─ ⏳ Ritirabile tra {remaining} minuti")
                            except:
                                pass
                    else:
                        print(f"⚪ {prefix}: Non annunciato")
    
    if advertised_count > 0:
        print(f"\n⚠️  {advertised_count} prefissi attualmente annunciati")
        print("   Potrebbero essere stati attivati per un attacco recente")
    else:
        print("\n✅ Tutti i prefissi sono in stato normale (non annunciati)")
    
    return advertised_count

def analyze_attack_likelihood():
    """
    Analisi probabilità di attacco basata su vari indicatori
    """
    print("\n🎯 ANALISI PROBABILITÀ ATTACCO")
    print("-" * 60)
    
    indicators = {
        'prefixes_advertised': False,
        'recent_ddos_events': False,
        'high_traffic': False,
        'dropped_packets': False
    }
    
    # 1. Controlla se ci sono prefissi annunciati
    advertised = check_prefix_status()
    if advertised > 0:
        indicators['prefixes_advertised'] = True
    
    # 2. Cerca eventi DDoS recenti
    if try_alternative_query(minutes_back=15):
        indicators['recent_ddos_events'] = True
    
    # Calcola probabilità
    active_indicators = sum(indicators.values())
    
    print("\n📊 RIEPILOGO INDICATORI:")
    print(f"  • Prefissi annunciati: {'🔴 Sì' if indicators['prefixes_advertised'] else '🟢 No'}")
    print(f"  • Eventi DDoS recenti: {'🔴 Sì' if indicators['recent_ddos_events'] else '🟢 No'}")
    
    print("\n🔮 VALUTAZIONE:")
    if active_indicators >= 2:
        print("  🚨 ALTA PROBABILITÀ di attacco in corso o recente")
        print("     Raccomandazione: Monitorare attentamente")
    elif active_indicators == 1:
        print("  ⚠️  POSSIBILE attività sospetta")
        print("     Raccomandazione: Verificare manualmente")
    else:
        print("  ✅ BASSA probabilità di attacco")
        print("     Situazione normale")

def main():
    print("=" * 60)
    print("CLOUDFLARE MAGIC TRANSIT - RILEVAMENTO ATTACCHI V2")
    print("=" * 60)
    print(f"Account: GOLINE SA")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Controlla analytics Magic Transit
    check_magic_transit_analytics(minutes_back=10)
    
    # Analisi completa
    analyze_attack_likelihood()
    
    print("\n" + "=" * 60)
    print("AZIONI DISPONIBILI")
    print("=" * 60)
    print("""
📌 Controllo continuo automatico:
   python3 /root/Cloudflare_MT_Integration/scripts/monitor.py

📌 Gestione manuale prefissi:
   python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py

📌 Ritira prefisso di test (se annunciato da >15 min):
   python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py withdraw-test
    """)

if __name__ == "__main__":
    main()