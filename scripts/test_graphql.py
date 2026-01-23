#!/usr/bin/env python3
"""
Test GraphQL queries per trovare quella corretta
"""

import requests
import json
from datetime import datetime, timedelta, timezone

ACCOUNT_ID = "YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN = "YOUR_API_TOKEN"
BASE_URL = "https://api.cloudflare.com/client/v4"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

print("=" * 60)
print("TEST GRAPHQL QUERIES PER MAGIC TRANSIT")
print("=" * 60)

# Test 1: Query base senza filter
print("\n1. TEST: dosdAttackAnalyticsGroups (senza filter)")
print("-" * 40)

query1 = """
query {
    viewer {
        accounts(filter: { accountTag: "%s" }) {
            dosdAttackAnalyticsGroups(
                limit: 5
                orderBy: [datetime_DESC]
            ) {
                dimensions {
                    attackId
                    datetime
                }
            }
        }
    }
}
""" % ACCOUNT_ID

response = requests.post(f"{BASE_URL}/graphql", headers=headers, json={"query": query1})
data = response.json()
if not data.get('errors'):
    print("✅ Query funzionante!")
    if data.get('data', {}).get('viewer', {}).get('accounts'):
        attacks = data['data']['viewer']['accounts'][0].get('dosdAttackAnalyticsGroups', [])
        print(f"   Trovati {len(attacks)} eventi")
        for attack in attacks[:2]:
            print(f"   - {attack.get('dimensions', {}).get('datetime', 'N/A')}")
else:
    print(f"❌ Errore: {data.get('errors')}")

# Test 2: Network Analytics v2
print("\n2. TEST: networkAnalyticsAdaptiveGroups")
print("-" * 40)

five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

query2 = """
query GetNetworkAnalytics($accountTag: string!, $datetimeStart: Time!) {
    viewer {
        accounts(filter: { accountTag: $accountTag }) {
            networkAnalyticsAdaptiveGroups(
                filter: {
                    datetime_geq: $datetimeStart
                }
                limit: 10
            ) {
                dimensions {
                    datetime
                    ipDestinationAddress
                    ipProtocol
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

variables2 = {
    "accountTag": ACCOUNT_ID,
    "datetimeStart": five_min_ago
}

response = requests.post(f"{BASE_URL}/graphql", headers=headers, json={
    "query": query2,
    "variables": variables2
})
data = response.json()
if not data.get('errors'):
    print("✅ Query funzionante!")
    if data.get('data', {}).get('viewer', {}).get('accounts'):
        events = data['data']['viewer']['accounts'][0].get('networkAnalyticsAdaptiveGroups', [])
        print(f"   Trovati {len(events)} eventi")
else:
    print(f"❌ Errore: {data.get('errors')}")

# Test 3: ipFlowsAdaptiveGroups
print("\n3. TEST: ipFlowsAdaptiveGroups")
print("-" * 40)

query3 = """
query GetIPFlows($accountTag: string!, $datetimeStart: Time!) {
    viewer {
        accounts(filter: { accountTag: $accountTag }) {
            ipFlowsAdaptiveGroups(
                filter: {
                    datetime_geq: $datetimeStart
                }
                limit: 10
                orderBy: [sum_packets_DESC]
            ) {
                dimensions {
                    datetime
                    ipDestinationAddress
                    ipSourceAddress
                    ipProtocol
                    outcome
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

variables3 = {
    "accountTag": ACCOUNT_ID,
    "datetimeStart": five_min_ago
}

response = requests.post(f"{BASE_URL}/graphql", headers=headers, json={
    "query": query3,
    "variables": variables3
})
data = response.json()
if not data.get('errors'):
    print("✅ Query funzionante!")
    if data.get('data', {}).get('viewer', {}).get('accounts'):
        flows = data['data']['viewer']['accounts'][0].get('ipFlowsAdaptiveGroups', [])
        print(f"   Trovati {len(flows)} flussi")
        for flow in flows[:3]:
            dims = flow.get('dimensions', {})
            metrics = flow.get('sum', {})
            print(f"   - {dims.get('ipDestinationAddress', 'N/A')}: {metrics.get('packets', 0):,} packets")
else:
    print(f"❌ Errore: {data.get('errors')}")

# Test 4: dosdNetworkAnalytics 
print("\n4. TEST: dosdNetworkAnalytics")
print("-" * 40)

query4 = """
query GetDosdAnalytics($accountTag: string!, $datetimeStart: Time!) {
    viewer {
        accounts(filter: { accountTag: $accountTag }) {
            dosdNetworkAnalytics(
                filter: {
                    datetime_geq: $datetimeStart
                }
                limit: 10
            ) {
                dimensions {
                    datetime
                    destinationIP
                    outcome
                    mitigationSystem
                }
                sum {
                    packets
                }
            }
        }
    }
}
"""

variables4 = {
    "accountTag": ACCOUNT_ID,
    "datetimeStart": five_min_ago
}

response = requests.post(f"{BASE_URL}/graphql", headers=headers, json={
    "query": query4,
    "variables": variables4
})
data = response.json()
if not data.get('errors'):
    print("✅ Query funzionante!")
    if data.get('data', {}).get('viewer', {}).get('accounts'):
        events = data['data']['viewer']['accounts'][0].get('dosdNetworkAnalytics', [])
        print(f"   Trovati {len(events)} eventi")
        for event in events[:3]:
            dims = event.get('dimensions', {})
            print(f"   - {dims.get('datetime', 'N/A')}: {dims.get('outcome', 'N/A')}")
else:
    print(f"❌ Errore: {data.get('errors')}")

# Test 5: flowtrackdNetworkAnalytics
print("\n5. TEST: flowtrackdNetworkAnalytics")
print("-" * 40)

query5 = """
query GetFlowTrackd($accountTag: string!, $datetimeStart: Time!) {
    viewer {
        accounts(filter: { accountTag: $accountTag }) {
            flowtrackdNetworkAnalytics(
                filter: {
                    datetime_geq: $datetimeStart
                }
                limit: 10
            ) {
                dimensions {
                    datetime
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

variables5 = {
    "accountTag": ACCOUNT_ID,
    "datetimeStart": five_min_ago
}

response = requests.post(f"{BASE_URL}/graphql", headers=headers, json={
    "query": query5,
    "variables": variables5
})
data = response.json()
if not data.get('errors'):
    print("✅ Query funzionante!")
    if data.get('data', {}).get('viewer', {}).get('accounts'):
        events = data['data']['viewer']['accounts'][0].get('flowtrackdNetworkAnalytics', [])
        print(f"   Trovati {len(events)} eventi")
else:
    print(f"❌ Errore: {data.get('errors')}")

print("\n" + "=" * 60)
print("RIEPILOGO")
print("=" * 60)
print("""
Le query funzionanti possono essere utilizzate per:
- Rilevare attacchi DDoS in corso
- Monitorare traffico anomalo
- Identificare prefissi sotto attacco
""")