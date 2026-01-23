#!/usr/bin/env python3
"""
Script per verificare attacchi DDoS in corso
Utilizza GraphQL API di Cloudflare per rilevare attività sospette
"""

import requests
import json
from datetime import datetime, timedelta
import sys

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def check_network_analytics(minutes_back=5):
    """
    Controlla Network Analytics per traffico anomalo
    """
    print(f"\n📊 NETWORK ANALYTICS (ultimi {minutes_back} minuti)")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    start_time = (datetime.utcnow() - timedelta(minutes=minutes_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = """
    query GetNetworkAnalytics($accountTag: string!, $datetimeStart: Time!, $datetimeEnd: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                magicTransitNetworkAnalytics: ipFlows1mGroups(
                    filter: {
                        datetime_geq: $datetimeStart
                        datetime_leq: $datetimeEnd
                    }
                    orderBy: [sum_packets_DESC]
                    limit: 10
                ) {
                    dimensions {
                        datetime
                        destinationIPAddress
                        sourceIPAddress
                        ipProtocol
                        outcome
                        attackMitigationType
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
                if accounts and accounts[0].get('magicTransitNetworkAnalytics'):
                    flows = accounts[0]['magicTransitNetworkAnalytics']
                    
                    if flows:
                        print(f"✅ Trovati {len(flows)} flussi di traffico significativi:\n")
                        
                        attack_detected = False
                        for flow in flows:
                            dims = flow.get('dimensions', {})
                            metrics = flow.get('sum', {})
                            
                            packets = metrics.get('packets', 0)
                            bits = metrics.get('bits', 0)
                            outcome = dims.get('outcome', '')
                            mitigation = dims.get('attackMitigationType', '')
                            
                            # Considera attacco se:
                            # - Outcome è "drop" (traffico bloccato)
                            # - Mitigation type presente
                            # - Alto volume di pacchetti (>100k in 1 minuto)
                            if outcome == 'drop' or mitigation or packets > 100000:
                                attack_detected = True
                                print(f"🚨 POSSIBILE ATTACCO:")
                                print(f"   Timestamp: {dims.get('datetime', 'N/A')}")
                                print(f"   Destinazione: {dims.get('destinationIPAddress', 'N/A')}")
                                print(f"   Sorgente: {dims.get('sourceIPAddress', 'N/A')}")
                                print(f"   Protocollo: {dims.get('ipProtocol', 'N/A')}")
                                print(f"   Outcome: {outcome}")
                                print(f"   Mitigazione: {mitigation or 'N/A'}")
                                print(f"   Pacchetti: {packets:,}")
                                print(f"   Bits: {bits:,}")
                                print()
                        
                        if not attack_detected:
                            print("✅ Nessun attacco rilevato nel periodo")
                    else:
                        print("ℹ️  Nessun flusso di traffico significativo")
                else:
                    print("ℹ️  Nessun dato disponibile")
            else:
                print(f"⚠️  Errori GraphQL: {data.get('errors')}")
                # Proviamo query alternativa
                return False
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    
    return True

def check_dosd_analytics(minutes_back=5):
    """
    Controlla DoS daemon analytics per attacchi mitigati
    """
    print(f"\n🛡️ DOSD ANALYTICS (ultimi {minutes_back} minuti)")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    start_time = (datetime.utcnow() - timedelta(minutes=minutes_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = """
    query GetDosdAnalytics($accountTag: string!, $datetimeStart: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                dosdNetworkAnalytics: ipFlows1mGroups(
                    filter: {
                        datetime_geq: $datetimeStart
                        outcome: "drop"
                    }
                    orderBy: [datetime_DESC]
                    limit: 100
                ) {
                    dimensions {
                        datetime
                        destinationIPAddress
                        sourceIPAddress
                        ipProtocol
                        outcome
                        destinationPort
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
        "datetimeStart": start_time
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
                if accounts and accounts[0].get('dosdNetworkAnalytics'):
                    events = accounts[0]['dosdNetworkAnalytics']
                    
                    if events:
                        print(f"🚨 Trovati {len(events)} eventi di mitigazione (traffico DROP):\n")
                        
                        # Raggruppa per IP destinazione
                        attacks_by_ip = {}
                        for event in events:
                            dims = event.get('dimensions', {})
                            metrics = event.get('sum', {})
                            dest_ip = dims.get('destinationIPAddress', 'Unknown')
                            
                            if dest_ip not in attacks_by_ip:
                                attacks_by_ip[dest_ip] = {
                                    'total_packets': 0,
                                    'total_bits': 0,
                                    'events': 0,
                                    'protocols': set(),
                                    'last_seen': dims.get('datetime', '')
                                }
                            
                            attacks_by_ip[dest_ip]['total_packets'] += metrics.get('packets', 0)
                            attacks_by_ip[dest_ip]['total_bits'] += metrics.get('bits', 0)
                            attacks_by_ip[dest_ip]['events'] += 1
                            attacks_by_ip[dest_ip]['protocols'].add(dims.get('ipProtocol', 'Unknown'))
                        
                        # Mostra risultati aggregati
                        for ip, info in sorted(attacks_by_ip.items(), 
                                              key=lambda x: x[1]['total_packets'], 
                                              reverse=True)[:5]:
                            print(f"🎯 Target IP: {ip}")
                            print(f"   Eventi: {info['events']}")
                            print(f"   Pacchetti bloccati: {info['total_packets']:,}")
                            print(f"   Bits bloccati: {info['total_bits']:,}")
                            print(f"   Protocolli: {', '.join(info['protocols'])}")
                            print(f"   Ultimo evento: {info['last_seen']}")
                            print()
                        
                        return True
                    else:
                        print("✅ Nessun evento di mitigazione nel periodo")
                else:
                    print("ℹ️  Nessun dato disponibile")
            else:
                print(f"⚠️  Errori GraphQL: {data.get('errors')}")
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
    
    return False

def check_attack_patterns():
    """
    Analizza pattern di attacco basati su soglie
    """
    print("\n🔍 ANALISI PATTERN ATTACCO")
    print("-" * 60)
    
    url = f"{BASE_URL}/graphql"
    
    # Controlla traffico dell'ultimo minuto con alta granularità
    one_minute_ago = (datetime.utcnow() - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    query = """
    query GetRecentTraffic($accountTag: string!, $datetimeStart: Time!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                ipFlows1mGroups(
                    filter: {
                        datetime_geq: $datetimeStart
                    }
                    orderBy: [sum_packets_DESC]
                    limit: 5
                ) {
                    dimensions {
                        datetime
                        destinationIPAddress
                        ipProtocol
                    }
                    sum {
                        packets
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "accountTag": ACCOUNT_ID,
        "datetimeStart": one_minute_ago
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
                if accounts and accounts[0].get('ipFlows1mGroups'):
                    flows = accounts[0]['ipFlows1mGroups']
                    
                    # Soglia: 12,000 pps = 720,000 pacchetti/minuto
                    ATTACK_THRESHOLD = 720000
                    
                    attack_detected = False
                    for flow in flows:
                        packets = flow.get('sum', {}).get('packets', 0)
                        if packets > ATTACK_THRESHOLD:
                            attack_detected = True
                            dims = flow.get('dimensions', {})
                            print(f"🚨 SUPERATA SOGLIA ATTACCO ({ATTACK_THRESHOLD:,} pkt/min):")
                            print(f"   IP Target: {dims.get('destinationIPAddress', 'N/A')}")
                            print(f"   Pacchetti/minuto: {packets:,}")
                            print(f"   Pacchetti/secondo: {packets//60:,}")
                            print(f"   Protocollo: {dims.get('ipProtocol', 'N/A')}")
                            print(f"   Timestamp: {dims.get('datetime', 'N/A')}")
                            print()
                    
                    if not attack_detected:
                        if flows:
                            top_flow = flows[0]
                            top_packets = top_flow.get('sum', {}).get('packets', 0)
                            print(f"✅ Traffico normale (picco: {top_packets:,} pkt/min)")
                            print(f"   Soglia attacco: {ATTACK_THRESHOLD:,} pkt/min")
                        else:
                            print("✅ Nessun traffico significativo")
                else:
                    print("ℹ️  Nessun dato disponibile")
            else:
                print(f"⚠️  Errori GraphQL: {data.get('errors')}")
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Errore: {e}")

def check_prefixes_under_attack():
    """
    Verifica quali dei nostri prefissi sono sotto attacco
    """
    print("\n📡 PREFISSI SOTTO ATTACCO")
    print("-" * 60)
    
    # Carica i nostri prefissi
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        our_prefixes = list(json.load(f)['prefixes'].keys())
    
    print(f"Monitoraggio prefissi: {', '.join(our_prefixes)}\n")
    
    url = f"{BASE_URL}/graphql"
    five_minutes_ago = (datetime.utcnow() - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Query specifica per i nostri prefissi
    for prefix in our_prefixes:
        # Estrai network base (es. 185.54.82 da 185.54.82.0/24)
        network_base = prefix.split('/')[0].rsplit('.', 1)[0] if '.' in prefix else prefix.split('/')[0]
        
        print(f"Controllo {prefix}...")
        
        query = """
        query CheckPrefixTraffic($accountTag: string!, $datetimeStart: Time!) {
            viewer {
                accounts(filter: { accountTag: $accountTag }) {
                    ipFlows1mGroups(
                        filter: {
                            datetime_geq: $datetimeStart
                        }
                        orderBy: [sum_packets_DESC]
                        limit: 100
                    ) {
                        dimensions {
                            destinationIPAddress
                            outcome
                        }
                        sum {
                            packets
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "accountTag": ACCOUNT_ID,
            "datetimeStart": five_minutes_ago
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
                    if accounts and accounts[0].get('ipFlows1mGroups'):
                        flows = accounts[0]['ipFlows1mGroups']
                        
                        # Filtra per IPs nel nostro prefisso
                        prefix_traffic = 0
                        prefix_drops = 0
                        
                        for flow in flows:
                            dest_ip = flow.get('dimensions', {}).get('destinationIPAddress', '')
                            if dest_ip.startswith(network_base):
                                packets = flow.get('sum', {}).get('packets', 0)
                                outcome = flow.get('dimensions', {}).get('outcome', '')
                                
                                prefix_traffic += packets
                                if outcome == 'drop':
                                    prefix_drops += packets
                        
                        if prefix_traffic > 0:
                            drop_percentage = (prefix_drops / prefix_traffic * 100) if prefix_traffic > 0 else 0
                            
                            if prefix_drops > 100000:  # Più di 100k pacchetti droppati
                                print(f"  🚨 SOTTO ATTACCO!")
                                print(f"     Traffico totale: {prefix_traffic:,} packets")
                                print(f"     Traffico bloccato: {prefix_drops:,} packets ({drop_percentage:.1f}%)")
                            elif prefix_traffic > 1000000:  # Alto traffico
                                print(f"  ⚠️  Traffico elevato")
                                print(f"     Totale: {prefix_traffic:,} packets")
                            else:
                                print(f"  ✅ Traffico normale ({prefix_traffic:,} packets)")
                        else:
                            print(f"  ✅ Nessun traffico rilevato")
                            
        except Exception as e:
            print(f"  ❌ Errore: {e}")
    
    print()

def main():
    print("=" * 60)
    print("CLOUDFLARE MAGIC TRANSIT - RILEVAMENTO ATTACCHI")
    print("=" * 60)
    print(f"Account: GOLINE SA")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Controllo ultimi 5 minuti di traffico")
    
    # Esegui tutti i controlli
    network_ok = check_network_analytics(minutes_back=5)
    
    if not network_ok:
        print("\n⚠️  Network Analytics non disponibile, provo metodi alternativi...")
        check_dosd_analytics(minutes_back=5)
    
    check_attack_patterns()
    check_prefixes_under_attack()
    
    print("=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    
    print("""
📌 Per monitoraggio continuo automatico:
   python3 /root/Cloudflare_MT_Integration/scripts/monitor.py

📌 Per controllo manuale prefissi:
   python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py status
    """)

if __name__ == "__main__":
    main()