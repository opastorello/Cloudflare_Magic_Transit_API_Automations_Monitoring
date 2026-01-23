#!/usr/bin/env python3
"""
Test di connettività API Cloudflare
Verifica token e recupera informazioni account
"""

import requests
import json
import sys
from datetime import datetime

# Configurazione
ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

# Headers per autenticazione
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def test_token():
    """Verifica validità del token"""
    print("\n1. TEST TOKEN")
    print("-" * 40)
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/tokens/verify"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✅ Token valido!")
            print(f"   Status: {data.get('result', {}).get('status', 'N/A')}")
            print(f"   ID: {data.get('result', {}).get('id', 'N/A')}")
        else:
            print("❌ Token non valido")
            print(f"   Errori: {data.get('errors', [])}")
            return False
    else:
        print(f"❌ Errore HTTP {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    return True

def get_account_info():
    """Recupera informazioni sull'account"""
    print("\n2. INFORMAZIONI ACCOUNT")
    print("-" * 40)
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            result = data.get("result", {})
            print(f"✅ Account trovato!")
            print(f"   Nome: {result.get('name', 'N/A')}")
            print(f"   ID: {result.get('id', 'N/A')}")
            print(f"   Tipo: {result.get('type', 'N/A')}")
            print(f"   Creato: {result.get('created_on', 'N/A')}")
        else:
            print("❌ Account non trovato")
            print(f"   Errori: {data.get('errors', [])}")
            return False
    else:
        print(f"❌ Errore HTTP {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    return True

def list_ip_prefixes():
    """Lista i prefissi IP configurati"""
    print("\n3. PREFISSI IP")
    print("-" * 40)
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            prefixes = data.get("result", [])
            if prefixes:
                print(f"✅ Trovati {len(prefixes)} prefissi:")
                for prefix in prefixes:
                    print(f"\n   Prefisso: {prefix.get('cidr', 'N/A')}")
                    print(f"   ID: {prefix.get('id', 'N/A')}")
                    print(f"   ASN: {prefix.get('asn', 'N/A')}")
                    print(f"   Descrizione: {prefix.get('description', 'N/A')}")
                    print(f"   LOA: {'✓' if prefix.get('loa_document_id') else '✗'}")
                    print(f"   Advertised: {prefix.get('advertised', 'N/A')}")
                    print(f"   Advertised Modified: {prefix.get('advertised_modified_at', 'N/A')}")
                return prefixes
            else:
                print("⚠️  Nessun prefisso trovato")
                print("   Potrebbe essere necessario configurare i prefissi IP")
        else:
            print("❌ Errore nel recupero prefissi")
            print(f"   Errori: {data.get('errors', [])}")
    else:
        print(f"❌ Errore HTTP {response.status_code}")
        if response.status_code == 403:
            print("   ⚠️  Permessi insufficienti - verificare che il token abbia accesso a IP Prefixes")
        print(f"   Response: {response.text}")
    
    return []

def check_bgp_prefixes(prefix_id):
    """Controlla i prefissi BGP per un dato prefix"""
    print(f"\n   Controllo BGP per prefix {prefix_id}:")
    
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/addressing/prefixes/{prefix_id}/bgp/prefixes"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            bgp_prefixes = data.get("result", [])
            if bgp_prefixes:
                print(f"   ✅ Trovati {len(bgp_prefixes)} BGP prefixes:")
                for bgp in bgp_prefixes:
                    print(f"      - CIDR: {bgp.get('cidr', 'N/A')}")
                    print(f"        ID: {bgp.get('id', 'N/A')}")
                    print(f"        On Demand: {'✓' if bgp.get('on_demand', {}).get('advertised') else '✗'}")
            else:
                print("   ⚠️  Nessun BGP prefix configurato")
        else:
            print(f"   ❌ Errore: {data.get('errors', [])}")
    else:
        print(f"   ❌ Errore HTTP {response.status_code}")

def check_magic_transit_status():
    """Verifica lo stato di Magic Transit"""
    print("\n4. STATO MAGIC TRANSIT")
    print("-" * 40)
    
    # Prova a recuperare informazioni su Magic Transit tramite GraphQL
    url = f"{BASE_URL}/graphql"
    
    query = """
    query GetAccountSettings($accountTag: string!) {
        viewer {
            accounts(filter: { accountTag: $accountTag }) {
                settings {
                    id
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
        if not data.get("errors"):
            print("✅ Accesso GraphQL funzionante")
        else:
            print("⚠️  GraphQL disponibile ma con errori:")
            for error in data.get("errors", []):
                print(f"   - {error.get('message', 'N/A')}")
    else:
        print(f"⚠️  GraphQL non accessibile (HTTP {response.status_code})")
        print("   Potrebbe essere necessario abilitare Magic Transit")

def save_config():
    """Salva la configurazione verificata"""
    print("\n5. SALVATAGGIO CONFIGURAZIONE")
    print("-" * 40)
    
    config = {
        "cloudflare": {
            "account_id": ACCOUNT_ID,
            "api_token": API_TOKEN,
            "verified_at": datetime.now().isoformat()
        },
        "test_results": {
            "token_valid": True,
            "account_accessible": True,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    config_path = "/root/Cloudflare_MT_Integration/config/settings.json"
    
    # Crea directory se non esiste
    import os
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configurazione salvata in: {config_path}")

def main():
    print("=" * 50)
    print("TEST CONNETTIVITÀ CLOUDFLARE API")
    print("=" * 50)
    print(f"Account: GOLINE SA ({ACCOUNT_ID})")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Esegui test
    if not test_token():
        print("\n❌ Test fallito: token non valido")
        sys.exit(1)
    
    if not get_account_info():
        print("\n❌ Test fallito: impossibile accedere all'account")
        sys.exit(1)
    
    # Lista prefissi e controlla BGP
    prefixes = list_ip_prefixes()
    if prefixes:
        for prefix in prefixes[:3]:  # Controlla solo i primi 3 per brevità
            prefix_id = prefix.get('id')
            if prefix_id:
                check_bgp_prefixes(prefix_id)
    
    # Controlla Magic Transit
    check_magic_transit_status()
    
    # Salva configurazione
    save_config()
    
    print("\n" + "=" * 50)
    print("✅ TEST COMPLETATO CON SUCCESSO!")
    print("=" * 50)
    print("\nProssimi passi:")
    print("1. Verificare che i prefissi siano configurati correttamente")
    print("2. Configurare i BGP prefixes se necessario")
    print("3. Implementare il monitor per il rilevamento attacchi")

if __name__ == "__main__":
    main()