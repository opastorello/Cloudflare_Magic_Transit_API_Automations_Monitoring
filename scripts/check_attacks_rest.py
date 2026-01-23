#!/usr/bin/env python3
"""
Rilevamento attacchi usando REST API e metodi alternativi
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

def check_firewall_events():
    """
    Controlla eventi firewall che potrebbero indicare un attacco
    """
    print("\n🔥 FIREWALL EVENTS")
    print("-" * 60)
    
    # Prova a ottenere eventi di sicurezza recenti
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/intel/attack-surface-report/issues"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                issues = data.get('result', [])
                if issues:
                    print(f"⚠️  Trovati {len(issues)} problemi di sicurezza")
                else:
                    print("✅ Nessun problema di sicurezza rilevato")
        else:
            print(f"ℹ️  API non disponibile (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Errore: {e}")

def check_logs_api():
    """
    Prova ad accedere ai logs
    """
    print("\n📝 LOGS API CHECK")
    print("-" * 60)
    
    # Endpoint per Logpush jobs
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/logpush/jobs"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                jobs = data.get('result', [])
                print(f"✅ Accesso Logs API funzionante")
                print(f"   Logpush jobs configurati: {len(jobs)}")
                
                for job in jobs:
                    if job.get('enabled'):
                        print(f"   - {job.get('name', 'N/A')}: {job.get('dataset', 'N/A')}")
            else:
                print("⚠️  Nessun logpush job configurato")
        else:
            print(f"ℹ️  Logpush non disponibile (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Errore: {e}")

def check_analytics_api():
    """
    Prova Analytics API v4 diretto
    """
    print("\n📊 ANALYTICS API V4")
    print("-" * 60)
    
    # Prova endpoint analytics
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    until = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/analytics/events"
    params = {
        "since": since,
        "until": until,
        "limit": 10
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                events = data.get('result', [])
                print(f"✅ Analytics API accessibile")
                print(f"   Eventi trovati: {len(events)}")
        else:
            print(f"ℹ️  Analytics events non disponibile (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Errore: {e}")

def check_magic_transit_status():
    """
    Controlla stato Magic Transit e prefissi
    """
    print("\n🛡️ MAGIC TRANSIT STATUS")
    print("-" * 60)
    
    # Controlla tutti i prefissi
    with open("/root/Cloudflare_MT_Integration/config/prefix_mapping.json", 'r') as f:
        prefix_map = json.load(f)['prefixes']
    
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
                        advertised_prefixes.append({
                            'prefix': prefix,
                            'modified_at': on_demand.get('advertised_modified_at'),
                            'description': info.get('description')
                        })
    
    if advertised_prefixes:
        print(f"🚨 {len(advertised_prefixes)} PREFISSI ATTUALMENTE ANNUNCIATI:")
        print("   (Probabilmente c'è stato un attacco recente)\n")
        
        for p in advertised_prefixes:
            print(f"   🟢 {p['prefix']} - {p['description']}")
            
            # Calcola da quanto tempo è annunciato
            if p['modified_at']:
                try:
                    announce_time = datetime.fromisoformat(p['modified_at'].replace('Z', '+00:00'))
                    elapsed = datetime.now(timezone.utc) - announce_time
                    minutes = int(elapsed.total_seconds() / 60)
                    
                    print(f"      Annunciato da: {minutes} minuti")
                    
                    # Se annunciato da meno di 30 minuti, probabilmente attacco in corso
                    if minutes < 30:
                        print(f"      ⚠️  POSSIBILE ATTACCO IN CORSO O RECENTE")
                    else:
                        print(f"      ℹ️  Attacco probabilmente terminato")
                        
                    if minutes >= 15:
                        print(f"      ✅ Può essere ritirato")
                    else:
                        print(f"      ⏳ Ritirabile tra {15-minutes} minuti")
                except:
                    pass
            print()
        
        return True
    else:
        print("✅ Nessun prefisso annunciato")
        print("   Situazione normale - nessun attacco rilevato")
        return False

def check_network_health():
    """
    Controlla health generale della rete
    """
    print("\n💚 NETWORK HEALTH CHECK")
    print("-" * 60)
    
    # Controlla connettività base
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                account = data.get('result', {})
                print(f"✅ Account: {account.get('name', 'N/A')}")
                print(f"   Tipo: {account.get('type', 'N/A')}")
                print(f"   ID: {account.get('id', 'N/A')}")
                
                # Controlla settings
                settings = account.get('settings', {})
                if settings:
                    print(f"   Settings configurati: {len(settings)}")
    except Exception as e:
        print(f"❌ Errore: {e}")

def analyze_attack_probability():
    """
    Analizza la probabilità di un attacco basandosi sui dati disponibili
    """
    print("\n" + "=" * 60)
    print("🎯 ANALISI PROBABILITÀ ATTACCO")
    print("=" * 60)
    
    # Controlla se ci sono prefissi annunciati
    attack_likely = check_magic_transit_status()
    
    if attack_likely:
        print("\n⚠️  ALTA PROBABILITÀ di attacco recente o in corso")
        print("   I prefissi BGP sono stati annunciati per mitigazione DDoS")
        print("\n   AZIONI CONSIGLIATE:")
        print("   1. Verificare i log del firewall")
        print("   2. Controllare il traffico di rete")
        print("   3. Attendere il ritiro automatico dei prefissi (15 min dopo fine attacco)")
    else:
        print("\n✅ BASSA probabilità di attacco")
        print("   Tutti i sistemi operano normalmente")

def main():
    print("=" * 60)
    print("CLOUDFLARE MAGIC TRANSIT - ATTACK DETECTION")
    print("=" * 60)
    print(f"Account: GOLINE SA")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Metodo: REST API + Status Analysis")
    
    # Esegui tutti i controlli
    check_network_health()
    check_firewall_events()
    check_logs_api()
    check_analytics_api()
    
    # Analisi finale
    analyze_attack_probability()
    
    print("\n" + "=" * 60)
    print("COMANDI DISPONIBILI")
    print("=" * 60)
    print("""
📌 Monitor automatico (consigliato):
   python3 /root/Cloudflare_MT_Integration/scripts/monitor.py
   
📌 Gestione manuale prefissi:
   python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py
   
📌 Ritira prefisso test (se >15 min):
   python3 /root/Cloudflare_MT_Integration/scripts/manual_control.py withdraw-test
    """)

if __name__ == "__main__":
    main()