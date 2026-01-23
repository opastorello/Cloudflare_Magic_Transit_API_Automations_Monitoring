#!/usr/bin/env python3
"""
Rilevamento attacchi DDoS usando le API GraphQL corrette per Magic Transit
Basato sulla documentazione ufficiale di Cloudflare Network Analytics v2
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

def check_magic_transit_analytics():
    """
    Query principale per Magic Transit Network Analytics
    Usa magicTransitNetworkAnalyticsAdaptiveGroups
    """
    print("\n🌐 MAGIC TRANSIT NETWORK ANALYTICS")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    
    # Ultimi 10 minuti
    datetime_start = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
    datetime_end = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = """
    query GetMagicTransitAnalytics($accountTag: string!, $datetimeStart: Time!, $datetimeEnd: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                magicTransitNetworkAnalyticsAdaptiveGroups(
                    filter: {
                        datetime_geq: $datetimeStart
                        datetime_leq: $datetimeEnd
                    }
                    limit: 50
                    orderBy: [sum_packets_DESC]
                ) {
                    dimensions {
                        datetime
                        ipDestinationAddress
                        ipSourceAddress
                        ipProtocol
                        outcome
                        mitigationSystem
                        direction
                        attackMitigationType
                        attackId
                    }
                    sum {
                        packets
                        bits
                    }
                    avg {
                        bitRateFiveMinutes
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "accountTag": ACCOUNT_ID,
        "datetimeStart": datetime_start,
        "datetimeEnd": datetime_end
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
                        print(f"✅ Trovati {len(analytics)} eventi di traffico\n")
                        
                        # Analizza eventi
                        dropped_traffic = []
                        attack_traffic = []
                        normal_traffic = []
                        
                        for event in analytics:
                            dims = event.get('dimensions', {})
                            metrics = event.get('sum', {})
                            
                            outcome = dims.get('outcome', '')
                            mitigation = dims.get('mitigationSystem', '')
                            attack_type = dims.get('attackMitigationType', '')
                            attack_id = dims.get('attackId', '')
                            
                            if outcome == 'drop' or attack_id or attack_type:
                                attack_traffic.append(event)
                            elif outcome == 'drop':
                                dropped_traffic.append(event)
                            else:
                                normal_traffic.append(event)
                        
                        # Mostra attacchi rilevati
                        if attack_traffic:
                            print(f"🚨 ATTACCHI RILEVATI: {len(attack_traffic)} eventi\n")
                            for event in attack_traffic[:5]:
                                dims = event.get('dimensions', {})
                                metrics = event.get('sum', {})
                                
                                print(f"   📍 IP Target: {dims.get('ipDestinationAddress', 'N/A')}")
                                print(f"      Sorgente: {dims.get('ipSourceAddress', 'N/A')}")
                                print(f"      Protocollo: {dims.get('ipProtocol', 'N/A')}")
                                print(f"      Pacchetti: {metrics.get('packets', 0):,}")
                                print(f"      Outcome: {dims.get('outcome', 'N/A')}")
                                print(f"      Attack ID: {dims.get('attackId', 'N/A')}")
                                print(f"      Attack Type: {dims.get('attackMitigationType', 'N/A')}")
                                print(f"      Mitigation: {dims.get('mitigationSystem', 'N/A')}")
                                print(f"      Timestamp: {dims.get('datetime', 'N/A')}")
                                print()
                            
                            return True  # Attacco rilevato
                        
                        # Mostra traffico droppato
                        if dropped_traffic:
                            print(f"⚠️  TRAFFICO BLOCCATO: {len(dropped_traffic)} eventi")
                            print(f"   (Potenziale attività sospetta)\n")
                            return True
                        
                        print(f"✅ Traffico normale: {len(normal_traffic)} eventi")
                        return False
                        
                    else:
                        print("ℹ️  Nessun evento nel periodo")
                        return False
                else:
                    print("ℹ️  Nessun dato account")
                    return False
            else:
                print(f"⚠️  Errori GraphQL: {data.get('errors')}")
                return False
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def check_dosd_attacks():
    """
    Query per DoSD Attack Analytics
    Usa dosdAttackAnalyticsGroups per metadata attacchi
    """
    print("\n🛡️ DOSD ATTACK ANALYTICS")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    
    # Query senza filter object come richiesto dall'errore
    query = """
    query GetDosdAttacks($accountTag: string!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                dosdAttackAnalyticsGroups(
                    limit: 10
                    orderBy: [startDatetime_DESC]
                ) {
                    dimensions {
                        attackId
                        attackType
                        startDatetime
                        endDatetime
                        destinationIP
                        sourceIP
                        action
                        protocol
                    }
                    sum {
                        packets
                        bits
                    }
                    avg {
                        packetsRate
                        bitsRate
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
                        print(f"📝 Ultimi {len(attacks)} attacchi DDoS registrati:\n")
                        
                        # Analizza attacchi recenti
                        recent_attacks = []
                        now = datetime.now(timezone.utc)
                        
                        for attack in attacks:
                            dims = attack.get('dimensions', {})
                            start_time_str = dims.get('startDatetime', '')
                            
                            if start_time_str:
                                try:
                                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                    time_diff = (now - start_time).total_seconds() / 60
                                    
                                    # Ultimi 30 minuti
                                    if time_diff <= 30:
                                        recent_attacks.append(attack)
                                except:
                                    pass
                        
                        if recent_attacks:
                            print(f"🚨 {len(recent_attacks)} ATTACCHI NEGLI ULTIMI 30 MINUTI:\n")
                            
                            for attack in recent_attacks:
                                dims = attack.get('dimensions', {})
                                metrics = attack.get('sum', {})
                                avg = attack.get('avg', {})
                                
                                print(f"   🆔 Attack ID: {dims.get('attackId', 'N/A')}")
                                print(f"      Tipo: {dims.get('attackType', 'N/A')}")
                                print(f"      IP Target: {dims.get('destinationIP', 'N/A')}")
                                print(f"      IP Sorgente: {dims.get('sourceIP', 'N/A')}")
                                print(f"      Protocollo: {dims.get('protocol', 'N/A')}")
                                print(f"      Azione: {dims.get('action', 'N/A')}")
                                print(f"      Inizio: {dims.get('startDatetime', 'N/A')}")
                                print(f"      Fine: {dims.get('endDatetime', 'In corso')}")
                                print(f"      Pacchetti totali: {metrics.get('packets', 0):,}")
                                print(f"      Bits totali: {metrics.get('bits', 0):,}")
                                print(f"      Rate pps: {avg.get('packetsRate', 0):,}")
                                print()
                            
                            return True  # Attacco recente trovato
                        else:
                            print("✅ Nessun attacco negli ultimi 30 minuti")
                            
                            if attacks:
                                last_attack = attacks[0]
                                dims = last_attack.get('dimensions', {})
                                print(f"\n   Ultimo attacco:")
                                print(f"   Data: {dims.get('startDatetime', 'N/A')}")
                                print(f"   Target: {dims.get('destinationIP', 'N/A')}")
                            
                            return False
                    else:
                        print("✅ Nessun attacco DDoS registrato")
                        return False
                else:
                    print("ℹ️  Nessun dato account")
                    return False
            else:
                print(f"⚠️  Errori: {data.get('errors')}")
                return False
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def check_tunnel_traffic():
    """
    Controlla il traffico sui tunnel Magic Transit
    """
    print("\n🚇 TUNNEL TRAFFIC ANALYSIS")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    
    datetime_start = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
    datetime_end = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = """
    query GetTunnelTraffic($accountTag: string!, $datetimeStart: Time!, $datetimeEnd: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                magicTransitTunnelTrafficAdaptiveGroups(
                    limit: 100
                    filter: {
                        datetime_geq: $datetimeStart
                        datetime_lt: $datetimeEnd
                        direction: "ingress"
                    }
                ) {
                    avg {
                        bitRateFiveMinutes
                    }
                    dimensions {
                        tunnelName
                        datetimeFiveMinutes
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "accountTag": ACCOUNT_ID,
        "datetimeStart": datetime_start,
        "datetimeEnd": datetime_end
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
                    tunnel_data = accounts[0].get('magicTransitTunnelTrafficAdaptiveGroups', [])
                    
                    if tunnel_data:
                        print(f"✅ Dati tunnel disponibili: {len(tunnel_data)} campioni")
                        
                        # Analizza traffico anomalo
                        high_traffic = []
                        for data_point in tunnel_data:
                            avg = data_point.get('avg', {})
                            dims = data_point.get('dimensions', {})
                            
                            bit_rate = avg.get('bitRateFiveMinutes', 0)
                            
                            # Considera alto traffico > 100 Mbps
                            if bit_rate > 100_000_000:
                                high_traffic.append({
                                    'tunnel': dims.get('tunnelName', 'N/A'),
                                    'time': dims.get('datetimeFiveMinutes', 'N/A'),
                                    'rate_mbps': bit_rate / 1_000_000
                                })
                        
                        if high_traffic:
                            print(f"\n⚠️  TRAFFICO ELEVATO RILEVATO:")
                            for ht in high_traffic[:3]:
                                print(f"   Tunnel: {ht['tunnel']}")
                                print(f"   Rate: {ht['rate_mbps']:.2f} Mbps")
                                print(f"   Time: {ht['time']}")
                            return True
                        else:
                            print("✅ Traffico tunnel normale")
                            return False
                    else:
                        print("ℹ️  Nessun dato tunnel disponibile")
                        return False
                else:
                    print("ℹ️  Nessun dato account")
                    return False
            else:
                print(f"⚠️  Errori: {data.get('errors')}")
                return False
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def analyze_prefixes():
    """
    Analizza quali prefissi potrebbero essere sotto attacco
    """
    print("\n📡 ANALISI PREFISSI")
    print("-" * 60)
    
    # Carica mappatura prefissi
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        prefix_map = json.load(f)['prefixes']
    
    # Controlla stato prefissi
    advertised_prefixes = []
    
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
                    
                    if on_demand.get('advertised'):
                        modified_at = on_demand.get('advertised_modified_at', '')
                        advertised_prefixes.append({
                            'prefix': prefix,
                            'modified_at': modified_at,
                            'description': info.get('description', 'N/A')
                        })
    
    if advertised_prefixes:
        print(f"🚨 {len(advertised_prefixes)} PREFISSI ANNUNCIATI (possibile attacco):\n")
        
        for p in advertised_prefixes:
            print(f"   🟢 {p['prefix']} - {p['description']}")
            
            if p['modified_at']:
                try:
                    announce_time = datetime.fromisoformat(p['modified_at'].replace('Z', '+00:00'))
                    elapsed = datetime.now(timezone.utc) - announce_time
                    minutes = int(elapsed.total_seconds() / 60)
                    
                    print(f"      Annunciato da: {minutes} minuti")
                    
                    if minutes < 30:
                        print(f"      ⚠️  Probabilmente sotto attacco")
                    else:
                        print(f"      ℹ️  Attacco probabilmente terminato")
                except:
                    pass
        print()
        return True
    else:
        print("✅ Nessun prefisso annunciato (nessun attacco)")
        return False

def main():
    print("=" * 60)
    print("🔍 CLOUDFLARE MAGIC TRANSIT - ATTACK DETECTION V3")
    print("=" * 60)
    print(f"Account: GOLINE SA ({ACCOUNT_ID})")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API: GraphQL Network Analytics v2")
    
    # Indicatori di attacco
    attack_indicators = {
        'magic_transit': False,
        'dosd_attacks': False,
        'tunnel_traffic': False,
        'prefixes_advertised': False
    }
    
    # Esegui controlli
    print("\nEsecuzione controlli...")
    
    attack_indicators['magic_transit'] = check_magic_transit_analytics()
    attack_indicators['dosd_attacks'] = check_dosd_attacks()
    attack_indicators['tunnel_traffic'] = check_tunnel_traffic()
    attack_indicators['prefixes_advertised'] = analyze_prefixes()
    
    # Valutazione finale
    print("=" * 60)
    print("📊 VALUTAZIONE FINALE")
    print("=" * 60)
    
    active_indicators = sum(attack_indicators.values())
    
    print("\nIndicatori:")
    print(f"  • Magic Transit Analytics: {'🔴 Attacco' if attack_indicators['magic_transit'] else '🟢 Normale'}")
    print(f"  • DoSD Attacks: {'🔴 Rilevati' if attack_indicators['dosd_attacks'] else '🟢 Nessuno'}")
    print(f"  • Tunnel Traffic: {'🔴 Anomalo' if attack_indicators['tunnel_traffic'] else '🟢 Normale'}")
    print(f"  • Prefissi BGP: {'🔴 Annunciati' if attack_indicators['prefixes_advertised'] else '🟢 Non annunciati'}")
    
    print(f"\n🎯 Risultato: {active_indicators}/4 indicatori attivi")
    
    if active_indicators >= 2:
        print("\n🚨 ALTA PROBABILITÀ DI ATTACCO IN CORSO")
        print("   Raccomandazione: Monitoraggio attivo richiesto")
    elif active_indicators == 1:
        print("\n⚠️  POSSIBILE ATTIVITÀ SOSPETTA")
        print("   Raccomandazione: Verificare manualmente")
    else:
        print("\n✅ SITUAZIONE NORMALE")
        print("   Nessun attacco rilevato")
    
    print("\n" + "=" * 60)
    print("📌 COMANDI UTILI")
    print("=" * 60)
    print("""
Monitor automatico:
  python3 /root/Cloudflare_MT_Integration/scripts/monitor.py

Controllo manuale prefissi:
  python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py

Test completo:
  python3 /root/Cloudflare_MT_Integration/scripts/test_system.py
    """)

if __name__ == "__main__":
    main()