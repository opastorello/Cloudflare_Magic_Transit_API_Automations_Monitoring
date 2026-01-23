# Cloudflare API Reference

**Version**: 2.0.0
**Last Updated**: 2026-01-22
**Author**: GOLINE SOC

---

## Table of Contents

1. [Authentication](#authentication)
2. [GraphQL Analytics API](#1-graphql-analytics-api)
3. [BGP Prefixes API](#2-bgp-prefixes-api)
4. [MNM Rules API](#3-mnm-rules-api)
5. [DDoS L3/4 Managed Ruleset API](#4-ddos-l34-managed-ruleset-api)
6. [DDoS Custom Overrides API](#5-ddos-custom-overrides-api) ⭐ NEW
7. [GRE Tunnels API](#6-gre-tunnels-api)
8. [IPsec Tunnels API](#7-ipsec-tunnels-api)
9. [Network Interconnects (CNI) API](#8-network-interconnects-cni-api)
10. [Tunnel Health Check GraphQL](#9-tunnel-health-check-graphql)
11. [Telegram Bot API](#10-telegram-bot-api)
12. [Wirefilter Expression Syntax](#wirefilter-expression-syntax) ⭐ NEW
13. [Rate Limits](#rate-limits)
14. [Error Codes](#error-codes)
15. [Scripts Using These APIs](#scripts-using-these-apis)
16. [References](#references)

---

## Authentication

### API Token (Recommended)

```http
Authorization: Bearer {API_TOKEN}
Content-Type: application/json
```

**Required Permissions:**
- `Account.Account Analytics:Read` - GraphQL queries
- `Account.Magic Transit Prefix:Read/Write` - BGP prefix management

### Global API Key (Required for some APIs)

```http
X-Auth-Email: {email}
X-Auth-Key: {global_api_key}
Content-Type: application/json
```

**Required for:**
- MNM Rules API
- DDoS Managed Ruleset API

---

## 1. GraphQL Analytics API

### Endpoint

```
POST https://api.cloudflare.com/client/v4/graphql
```

### 1.1 DDoS Network Analytics (Dropped Traffic)

**Used by:** `cloudflare-network-analytics-monitor.py`

```graphql
query NetworkAnalytics($accountTag: String!, $since: Time!, $until: Time!) {
    viewer {
        accounts(filter: {accountTag: $accountTag}) {
            dosdNetworkAnalyticsAdaptiveGroups(
                filter: {
                    datetime_geq: $since
                    datetime_leq: $until
                    outcome: "drop"
                }
                limit: 1000
                orderBy: [datetime_DESC]
            ) {
                dimensions {
                    datetime
                    attackId
                    attackVector
                    ipProtocolName
                    tcpFlagsString
                    ipSourceAddress
                    sourcePort
                    sourceAsn
                    sourceAsnName
                    sourceCountry
                    ipDestinationAddress
                    destinationPort
                    coloCode
                    coloCountry
                    coloCity
                    ruleName
                    ruleId
                    outcome
                    verdict
                    mitigationReason
                }
                sum {
                    packets
                    bits
                }
            }
        }
    }
}
```

**Variables:**

| Variable | Type | Example |
|----------|------|---------|
| `accountTag` | String | `"YOUR_ACCOUNT_ID"` |
| `since` | Time (ISO8601) | `"2026-01-21T00:00:00Z"` |
| `until` | Time (ISO8601) | `"2026-01-21T23:59:59Z"` |

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `datetime` | String | Event timestamp (ISO8601) |
| `attackId` | String | Unique attack identifier |
| `attackVector` | String | Attack type (SYN Flood, UDP Flood, etc.) |
| `ipProtocolName` | String | Protocol (TCP, UDP, ICMP, GRE) |
| `tcpFlagsString` | String | TCP flags (SYN, ACK, PSH,ACK, etc.) |
| `ipSourceAddress` | String | Source IP address |
| `sourcePort` | Integer | Source port |
| `sourceAsn` | Integer | Source ASN number (v1.3.6) |
| `sourceAsnName` | String | Source ASN organization name (v1.3.6) |
| `sourceCountry` | String | Source country ISO code (v1.3.6) |
| `ipDestinationAddress` | String | Destination IP address |
| `destinationPort` | Integer | Destination port |
| `coloCode` | String | Cloudflare datacenter code |
| `coloCountry` | String | Cloudflare datacenter country |
| `coloCity` | String | Cloudflare datacenter city |
| `ruleName` | String | DDoS rule name |
| `ruleId` | String | DDoS rule ID |
| `outcome` | String | Traffic outcome (drop, pass) |
| `verdict` | String | Final verdict (drop, pass) |
| `mitigationReason` | String | Mitigation action taken |
| `sum.packets` | Integer | Dropped packets count |
| `sum.bits` | Integer | Dropped bits count |

### 1.2 Magic Transit Network Analytics

**Used by:** `cloudflare-autowithdraw.py`, `dashboard/app.py`

```graphql
query MagicTransitAnalytics($accountTag: String!, $since: Time!, $until: Time!) {
    viewer {
        accounts(filter: {accountTag: $accountTag}) {
            magicTransitNetworkAnalyticsAdaptiveGroups(
                filter: {
                    datetime_geq: $since
                    datetime_leq: $until
                }
                limit: 10000
                orderBy: [datetime_DESC]
            ) {
                dimensions {
                    datetime
                    coloCode
                    destinationAddress
                    outcome
                    verdict
                }
                sum {
                    packets
                    bits
                }
            }
        }
    }
}
```

### 1.3 MNM Flow Data

**Used by:** `dashboard/app.py` (Network Flow stats)

```graphql
query MNMFlowData($accountTag: String!, $since: Time!, $until: Time!) {
    viewer {
        accounts(filter: {accountTag: $accountTag}) {
            total: mnmFlowDataAdaptiveGroups(
                filter: {datetime_geq: $since, datetime_leq: $until}
                limit: 1
            ) {
                sum { bits packets }
            }
            byProtocol: mnmFlowDataAdaptiveGroups(
                filter: {datetime_geq: $since, datetime_leq: $until}
                limit: 10
                orderBy: [sum_bits_DESC]
            ) {
                dimensions { protocolString }
                sum { bits packets }
            }
            bySource: mnmFlowDataAdaptiveGroups(
                filter: {datetime_geq: $since, datetime_leq: $until}
                limit: 10
                orderBy: [sum_bits_DESC]
            ) {
                dimensions { sourceAddress }
                sum { bits packets }
            }
            byRouter: mnmFlowDataAdaptiveGroups(
                filter: {datetime_geq: $since, datetime_leq: $until}
                limit: 10
                orderBy: [sum_bits_DESC]
            ) {
                dimensions { routerAddress }
                sum { bits packets }
            }
            byDestination: mnmFlowDataAdaptiveGroups(
                filter: {datetime_geq: $since, datetime_leq: $until}
                limit: 10
                orderBy: [sum_bits_DESC]
            ) {
                dimensions { destinationAddress }
                sum { bits packets }
            }
        }
    }
}
```

**Available Dimensions:**

| Dimension | Description |
|-----------|-------------|
| `protocolString` | Protocol name (TCP, UDP, ICMP, ESP, GRE) |
| `sourceAddress` | Source IP address |
| `destinationAddress` | Destination IP address |
| `routerAddress` | Router IP (GOLINE: 185.54.80.1, 185.54.80.2) |
| `tcpFlagsString` | TCP flags (ACK, SYN, PSH,ACK, etc.) |

---

## 2. BGP Prefixes API

### Base URLs

Cloudflare uses a hierarchical prefix structure:

```
/accounts/{account_id}/addressing/prefixes                              # Parent prefixes
/accounts/{account_id}/addressing/prefixes/{prefix_id}/bgp/prefixes     # BGP prefixes under parent
/accounts/{account_id}/addressing/prefixes/{prefix_id}/bgp/status       # BGP status (alternative)
```

### 2.1 List Parent Prefixes

**Used by:** `cloudflare-network-analytics-monitor.py`, `cloudflare-autowithdraw.py`

```http
GET /accounts/{account_id}/addressing/prefixes
```

**Response:**

```json
{
  "success": true,
  "result": [
    {
      "id": "parent_prefix_id",
      "cidr": "185.54.80.0/22",
      "description": "GOLINE IPv4 Block",
      "account_id": "...",
      "advertised": false,
      "on_demand": {
        "advertised": false
      }
    }
  ]
}
```

### 2.2 List BGP Prefixes

```http
GET /accounts/{account_id}/addressing/prefixes/{parent_prefix_id}/bgp/prefixes
```

**Response:**

```json
{
  "success": true,
  "result": [
    {
      "id": "prefix_id_123",
      "prefix": "185.54.80.0/24",
      "description": "BGP",
      "advertised": false,
      "on_demand": {
        "advertised": false,
        "advertised_modified_at": "2026-01-20T22:03:13Z"
      },
      "asn": 202032
    }
  ]
}
```

### 2.3 Advertise/Withdraw Prefix (Method 1 - Per BGP Prefix)

**Used by:** `cloudflare-prefix-manager.py`

```http
PATCH /accounts/{account_id}/addressing/prefixes/{parent_prefix_id}/bgp/prefixes/{bgp_prefix_id}
```

**Request Body:**

```json
{
  "advertised": true
}
```

| Value | Action |
|-------|--------|
| `true` | Advertise prefix |
| `false` | Withdraw prefix |

### 2.4 Advertise/Withdraw Prefix (Method 2 - BGP Status)

**Used by:** `cloudflare-autowithdraw.py`

```http
PATCH /accounts/{account_id}/addressing/prefixes/{parent_prefix_id}/bgp/status
```

**Request Body:**

```json
{
  "advertised": true
}
```

**Note:** Both PATCH endpoints accomplish the same result. Method 1 targets a specific BGP prefix, while Method 2 targets the parent prefix's BGP status directly.

### 2.5 15-Minute Re-Advertisement Constraint

Cloudflare enforces a **15-minute cooldown** after withdrawing a prefix before it can be re-advertised.

**Error Response (HTTP 429):**

```json
{
  "success": false,
  "errors": [
    {
      "code": 1002,
      "message": "Prefix was withdrawn less than 15 minutes ago"
    }
  ]
}
```

### GOLINE Prefix Mapping

| Prefix | Description | Status |
|--------|-------------|--------|
| `185.54.80.0/24` | BGP | On-Demand |
| `185.54.81.0/24` | DMZ | On-Demand |
| `185.54.82.0/24` | DMZ-EXT | On-Demand |
| `185.54.83.0/24` | DMZ EXT2 | On-Demand |
| `2a02:4460:1::/48` | DMZv6 | On-Demand |

---

## 3. MNM Rules API

### Base URL

```
https://api.cloudflare.com/client/v4/accounts/{account_id}/mnm/rules
```

**Authentication:** Global API Key required

### 3.1 Rule Types

#### Threshold Rules (BPS/PPS)

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | `"threshold"` |
| `name` | string | Rule name |
| `prefixes` | array | BGP prefixes to protect |
| `bandwidth_threshold` | number | Bits per second (BPS) |
| `packet_threshold` | number | Packets per second (PPS) |
| `duration` | string | Time before triggering (e.g., `"1m0s"`) |
| `automatic_advertisement` | boolean | Enable auto BGP advertisement |

#### Advanced DDoS Rules (sFlow)

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | `"advanced_ddos"` |
| `name` | string | Rule name |
| `prefixes` | array | BGP prefixes to protect |
| `automatic_advertisement` | boolean | Enable auto BGP advertisement |
| `prefix_match` | string | `"subnet"` or `"exact"` |

### 3.2 List Rules

```http
GET /accounts/{account_id}/mnm/rules
```

### 3.3 Create Rule

```http
POST /accounts/{account_id}/mnm/rules
```

**BPS Rule:**

```json
{
  "name": "DDoS Protection BPS 185.54.80.0-24",
  "type": "threshold",
  "prefixes": ["185.54.80.0/24"],
  "bandwidth_threshold": 4000000000,
  "duration": "1m0s",
  "automatic_advertisement": true
}
```

**sFlow Rule:**

```json
{
  "name": "sFlow-DDoS-Attack-IPv4",
  "type": "advanced_ddos",
  "prefixes": ["185.54.80.0/24"],
  "automatic_advertisement": true,
  "prefix_match": "subnet"
}
```

### 3.4 Update Rule

```http
PATCH /accounts/{account_id}/mnm/rules/{rule_id}
```

**Request Body (partial update - only include fields to change):**

```json
{
  "bandwidth_threshold": 5000000000,
  "duration": "2m0s",
  "automatic_advertisement": false
}
```

**Updatable Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `bandwidth_threshold` | number | Bits per second (1-100 Gbps) |
| `packet_threshold` | number | Packets per second (10k-10M pps) |
| `duration` | string | Time before triggering (e.g., `"5m0s"`) |
| `automatic_advertisement` | boolean | Enable/disable auto BGP advertisement |

**Response:**

```json
{
  "success": true,
  "result": {
    "id": "rule_id",
    "name": "DDoS Protection BPS 185.54.80.0-24",
    "type": "threshold",
    "prefixes": ["185.54.80.0/24"],
    "bandwidth_threshold": 5000000000,
    "duration": "2m0s",
    "automatic_advertisement": false
  }
}
```

**Note:** Only include fields you want to update. Omitted fields retain their current values.

### 3.5 Delete Rule

```http
DELETE /accounts/{account_id}/mnm/rules/{rule_id}
```

### Validation Limits

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| `bandwidth_threshold` | 1 | 100 | Gbps |
| `packet_threshold` | 10 | 10,000 | kpps |
| `duration` | 1 | 60 | minutes |

### Current GOLINE Rules (12 total)

| Prefix | BPS | PPS | sFlow |
|--------|-----|-----|-------|
| 185.54.80.0/24 | 4 Gbps / 1 min | 500k pps / 1 min | Yes |
| 185.54.81.0/24 | 4 Gbps / 1 min | 500k pps / 1 min | Yes |
| 185.54.82.0/24 | 4 Gbps / 1 min | 500k pps / 1 min | - |
| 185.54.83.0/24 | 4 Gbps / 1 min | 500k pps / 1 min | - |
| 2a02:4460:1::/48 | 4 Gbps / 1 min | 500k pps / 1 min | - |

---

## 4. DDoS L3/4 Managed Ruleset API

### Ruleset IDs

| Ruleset | ID |
|---------|-----|
| **DDoS L3/4 Managed Ruleset** | `3b64149bfa6e4220bbbc2bd6db589552` |
| **Account Root Ruleset** | `108b5719d12e4169a0ac2e4f499d8bae` |

### 4.1 Get Managed Ruleset

```http
GET /accounts/{account_id}/rulesets/3b64149bfa6e4220bbbc2bd6db589552
```

**Response:**

```json
{
  "success": true,
  "result": {
    "id": "3b64149bfa6e4220bbbc2bd6db589552",
    "name": "Cloudflare L3/4 DDoS Managed Ruleset",
    "rules": [
      {
        "id": "afd7c2341e974f1c985c338934228119",
        "ref": "UDP4-0002",
        "description": "IPv4 UDP SIP traffic",
        "action": "log",
        "enabled": true,
        "categories": ["sip"],
        "allowed_override_actions": ["block", "ddos_dynamic", "log"]
      }
    ]
  }
}
```

### 4.2 Actions

| Action | Description |
|--------|-------------|
| `block` | Block immediately |
| `log` | Log only (no blocking) |
| `ddos_dynamic` | Dynamic protection (auto-adjust) |

### 4.3 Sensitivity Levels (for ddos_dynamic only)

| API Value | UI Label | Description |
|-----------|----------|-------------|
| `default` | High | Most aggressive |
| `medium` | Medium | Balanced |
| `low` | Low | Less aggressive |
| `eoff` | Essentially Off | Near disabled |

### 4.4 Apply Override

```http
PUT /accounts/{account_id}/rulesets/108b5719d12e4169a0ac2e4f499d8bae
```

**Request Body:**

```json
{
  "rules": [
    {
      "action": "execute",
      "action_parameters": {
        "id": "3b64149bfa6e4220bbbc2bd6db589552",
        "overrides": {
          "rules": [
            {
              "id": "afd7c2341e974f1c985c338934228119",
              "action": "ddos_dynamic",
              "sensitivity_level": "low"
            }
          ]
        }
      },
      "expression": "true",
      "enabled": true
    }
  ]
}
```

### Editable Rules Summary

| Category | Count | allowed_override_actions |
|----------|-------|--------------------------|
| Full control | 15 | `["block", "ddos_dynamic", "log"]` |
| Block/Log only | 14 | `["block", "log"]` |
| Read-only | 95 | `null` or `[]` |
| **Total** | **124** | |

---

## 5. DDoS Custom Overrides API

Custom overrides allow you to create rules with **custom expressions** that target specific IPs, protocols, or ports with modified DDoS sensitivity settings. These are stored in the **Account Root Ruleset**.

### Ruleset IDs

| Ruleset | ID | Purpose |
|---------|-----|---------|
| **DDoS L3/4 Managed Ruleset** | `3b64149bfa6e4220bbbc2bd6db589552` | Contains 124 managed rules |
| **Account Root Ruleset** | `108b5719d12e4169a0ac2e4f499d8bae` | Stores custom overrides |

### 5.1 Get Custom Overrides

```http
GET /accounts/{account_id}/rulesets/{root_ruleset_id}
```

**Headers:**

```http
X-Auth-Email: {email}
X-Auth-Key: {global_api_key}
```

**Response:**

```json
{
  "success": true,
  "result": {
    "id": "108b5719d12e4169a0ac2e4f499d8bae",
    "name": "root",
    "kind": "root",
    "phase": "ddos_l4",
    "version": "41",
    "rules": [
      {
        "id": "8de19f5bcbb24d80b1c439e88b475b56",
        "description": "IPSec VPN Gateway (Low sensitivity)",
        "enabled": true,
        "expression": "ip.dst eq 185.54.80.30 and ip.proto.num eq 50",
        "action": "execute",
        "action_parameters": {
          "id": "3b64149bfa6e4220bbbc2bd6db589552",
          "overrides": {
            "rules": [
              {
                "id": "89bd10e19f974b9ba3784db068c2fd70",
                "sensitivity_level": "low"
              }
            ]
          },
          "version": "latest"
        },
        "version": "4",
        "last_updated": "2026-01-22T00:43:13Z"
      }
    ]
  }
}
```

### 5.2 Custom Override Rule Structure

Each custom override rule has the following structure:

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `description` | string | Yes | Human-readable rule name |
| `expression` | string | Yes | Wirefilter expression (see syntax below) |
| `enabled` | boolean | Yes | Enable/disable the rule |
| `action` | string | Yes | Always `"execute"` |
| `action_parameters.id` | string | Yes | ID of managed ruleset to override |
| `action_parameters.overrides.rules` | array | Yes | Array of rule overrides |
| `action_parameters.overrides.rules[].id` | string | Yes | Target managed rule ID |
| `action_parameters.overrides.rules[].sensitivity_level` | string | No | Sensitivity level |
| `action_parameters.overrides.rules[].action` | string | No | Override action |

### 5.3 Create Custom Override

```http
PUT /accounts/{account_id}/rulesets/{root_ruleset_id}
```

**Request Body (adds new rule to existing rules):**

```json
{
  "rules": [
    {
      "description": "Web Server Protection (Low sensitivity)",
      "expression": "ip.dst eq 185.54.81.15 and tcp.dstport in {80 443}",
      "enabled": true,
      "action": "execute",
      "action_parameters": {
        "id": "3b64149bfa6e4220bbbc2bd6db589552",
        "overrides": {
          "rules": [
            {
              "id": "9da0fb429a25436fa543519f4570f19f",
              "sensitivity_level": "low"
            }
          ]
        },
        "version": "latest"
      }
    }
  ]
}
```

**Important:** PUT replaces ALL rules. To add a new rule:
1. GET current ruleset
2. Append new rule to `rules` array
3. PUT the complete array

### 5.4 Update Custom Override

To update a single rule while preserving others:

1. GET current ruleset
2. Find the rule by ID
3. Modify the desired fields
4. PUT the complete rules array

**Example - Update expression and sensitivity:**

```json
{
  "rules": [
    {
      "id": "existing_rule_id",
      "description": "Updated Rule Name",
      "expression": "ip.dst eq 185.54.81.15 and tcp.dstport in {80 443 8080}",
      "enabled": true,
      "action": "execute",
      "action_parameters": {
        "id": "3b64149bfa6e4220bbbc2bd6db589552",
        "overrides": {
          "rules": [
            {
              "id": "9da0fb429a25436fa543519f4570f19f",
              "sensitivity_level": "medium"
            }
          ]
        },
        "version": "latest"
      }
    }
  ]
}
```

### 5.5 Delete Custom Override

To delete a rule:
1. GET current ruleset
2. Remove the rule from the `rules` array
3. PUT the remaining rules

### 5.6 Reorder Rules (Position API)

**IMPORTANT:** Rule order matters! Cloudflare evaluates rules top-to-bottom and applies the **first match**. More specific rules should come before generic rules.

```http
PATCH /accounts/{account_id}/rulesets/{root_ruleset_id}/rules/{rule_id}
```

**Request Body - Move to specific position (1-based):**

```json
{
  "position": {
    "index": 1
  }
}
```

**Request Body - Move before another rule:**

```json
{
  "position": {
    "before": "target_rule_id"
  }
}
```

**Request Body - Move after another rule:**

```json
{
  "position": {
    "after": "target_rule_id"
  }
}
```

**Request Body - Move to first position:**

```json
{
  "position": {
    "before": ""
  }
}
```

**Request Body - Move to last position:**

```json
{
  "position": {
    "after": ""
  }
}
```

**Position Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `index` | integer | Move to exact position (1-based) |
| `before` | string | Move before specified rule ID (empty = first) |
| `after` | string | Move after specified rule ID (empty = last) |

**Note:** Only ONE position parameter can be used per request.

### 5.7 Target Rule IDs (DDoS Managed Rules)

These are the managed rule IDs you can target with custom overrides:

| Rule ID | Name | Protocol | Description |
|---------|------|----------|-------------|
| `9da0fb429a25436fa543519f4570f19f` | TCP-0001 | TCP | TCP SYN flood |
| `6efeb57a52e744e89a5413121bd0b3d3` | TCP-0002 | TCP | TCP out-of-state flood |
| `599dab0942ff4898ac1b7797e954e98b` | UDP-0001 | UDP | Generic UDP flood |
| `520f5ecec28844ca971a8b3f9c425c26` | DNS-0002 | UDP | DNS flood |
| `afd7c2341e974f1c985c338934228119` | SIP-0002 | UDP | SIP flood |
| `89bd10e19f974b9ba3784db068c2fd70` | ESP4-0001 | ESP | IPv4 ESP flood |
| `63996ad8353d42e08188bd6bdcd96fe2` | ESP6-0001 | ESP | IPv6 ESP flood |
| `cdc6573a5b60439d80eb792d70534fe6` | UDP4-0001 | UDP | IPv4 UDP fragments |
| `c2671098563b405a8b0600f550d7ad86` | UDP6-0001 | UDP | IPv6 UDP fragments |
| `90c9e55497724742b60f603fe4e7541c` | ENT-0004 | Any | Enterprise rule 4 |
| `f526ae90584b401d8d7dd9f4938e978c` | ENT-0005 | Any | Enterprise rule 5 |

### 5.8 Sensitivity Levels

| API Value | UI Label | Description |
|-----------|----------|-------------|
| `default` | High | Most aggressive protection |
| `medium` | Medium | Balanced protection |
| `low` | Low | Less aggressive, fewer false positives |
| `eoff` | Essentially Off | Minimal protection |

### 5.9 Complete Example - Create Web Server Override

**Step 1: GET current rules**

```bash
curl -X GET "https://api.cloudflare.com/client/v4/accounts/{account_id}/rulesets/108b5719d12e4169a0ac2e4f499d8bae" \
  -H "X-Auth-Email: YOUR_EMAIL" \
  -H "X-Auth-Key: {api_key}"
```

**Step 2: Add new rule and PUT**

```bash
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/{account_id}/rulesets/108b5719d12e4169a0ac2e4f499d8bae" \
  -H "X-Auth-Email: YOUR_EMAIL" \
  -H "X-Auth-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [
      {
        "description": "Mail Server SMTP Protection",
        "expression": "ip.dst eq 185.54.81.5 and tcp.dstport in {25 465 587}",
        "enabled": true,
        "action": "execute",
        "action_parameters": {
          "id": "3b64149bfa6e4220bbbc2bd6db589552",
          "overrides": {
            "rules": [
              {
                "id": "9da0fb429a25436fa543519f4570f19f",
                "sensitivity_level": "low"
              }
            ]
          },
          "version": "latest"
        }
      }
    ]
  }'
```

### 5.10 Expression Validation

Before creating a rule, validate the expression:

```http
POST /accounts/{account_id}/rulesets/{root_ruleset_id}/rules
```

**Request Body:**

```json
{
  "expression": "ip.dst eq 185.54.81.15 and tcp.dstport in {80 443}",
  "action": "skip"
}
```

If the expression is invalid, Cloudflare returns an error with details.

### Rule Order Best Practices

1. **Most specific rules first** - Rules matching specific ports before rules matching all traffic
2. **Protocol-specific before generic** - TCP port rules before "all TCP" rules
3. **Single IP before ranges** - `ip.dst eq X` before `ip.dst in {X Y Z}`

**Example correct order:**

```
1. ip.dst eq 185.54.81.15 and tcp.dstport in {8080 5060}  ← Specific ports
2. ip.dst eq 185.54.81.15 and tcp.dstport in {80 443}     ← Web ports
3. ip.dst eq 185.54.81.15                                  ← All traffic (catch-all)
```

**Example incorrect order:**

```
1. ip.dst eq 185.54.81.15                                  ← Matches everything!
2. ip.dst eq 185.54.81.15 and tcp.dstport in {80 443}     ← Never reached
3. ip.dst eq 185.54.81.15 and tcp.dstport in {8080 5060}  ← Never reached
```

---

## 6. GRE Tunnels API

### Base URL

```
https://api.cloudflare.com/client/v4/accounts/{account_id}/magic/gre_tunnels
```

**Authentication:** API Token (Magic Transit Read/Write)

### 5.1 List GRE Tunnels

```http
GET /accounts/{account_id}/magic/gre_tunnels
```

**Headers:**

```http
Authorization: Bearer {API_TOKEN}
x-magic-new-hc-target: true  (optional)
```

**Response:**

```json
{
  "success": true,
  "result": {
    "gre_tunnels": [
      {
        "id": "string",
        "name": "gre-tunnel-1",
        "description": "Primary GRE tunnel",
        "cloudflare_gre_endpoint": "162.159.X.X",
        "customer_gre_endpoint": "185.54.81.X",
        "interface_address": "10.0.0.1/31",
        "interface_address6": "2001:db8::1/127",
        "mtu": 1476,
        "ttl": 64,
        "automatic_return_routing": true,
        "created_on": "2026-01-15T10:00:00Z",
        "modified_on": "2026-01-20T15:30:00Z",
        "bgp": {
          "customer_asn": 202032,
          "md5_key": "secret",
          "extra_prefixes": ["185.54.80.0/22"]
        },
        "bgp_status": {
          "state": "BGP_UP",
          "tcp_established": true,
          "updated_at": "2026-01-21T10:00:00Z",
          "cf_speaker_ip": "10.0.0.0",
          "cf_speaker_port": 179,
          "customer_speaker_ip": "10.0.0.1",
          "customer_speaker_port": 179
        },
        "health_check": {
          "enabled": true,
          "type": "reply",
          "rate": "mid",
          "direction": "bidirectional",
          "target": {
            "saved": "10.0.0.1",
            "effective": "10.0.0.1"
          }
        }
      }
    ]
  }
}
```

### 5.2 Get Single GRE Tunnel

```http
GET /accounts/{account_id}/magic/gre_tunnels/{gre_tunnel_id}
```

### 5.3 Create GRE Tunnel

```http
POST /accounts/{account_id}/magic/gre_tunnels
```

**Request Body:**

```json
{
  "name": "gre-tunnel-new",
  "description": "New GRE tunnel",
  "cloudflare_gre_endpoint": "162.159.X.X",
  "customer_gre_endpoint": "185.54.81.X",
  "interface_address": "10.0.0.2/31",
  "mtu": 1476,
  "ttl": 64,
  "health_check": {
    "enabled": true,
    "type": "reply",
    "rate": "mid"
  }
}
```

### 5.4 Update GRE Tunnel

```http
PUT /accounts/{account_id}/magic/gre_tunnels/{gre_tunnel_id}
```

**Request Body (all required fields must be included):**

```json
{
  "name": "gre-tunnel-1",
  "cloudflare_gre_endpoint": "162.159.X.X",
  "customer_gre_endpoint": "185.54.81.X",
  "interface_address": "10.0.0.1/31",
  "description": "Updated description",
  "ttl": 64,
  "mtu": 1476,
  "health_check": {
    "enabled": true,
    "target": "185.54.81.X",
    "type": "reply",
    "rate": "mid",
    "direction": "unidirectional"
  }
}
```

**Editable Fields:**

| Field | Required | Type | Editable | Notes |
|-------|:--------:|------|:--------:|-------|
| `name` | Yes | string | ✅ | Tunnel display name |
| `cloudflare_gre_endpoint` | Yes | IP | ❌ | Assigned by Cloudflare |
| `customer_gre_endpoint` | Yes | IP | ✅ | Customer router IP |
| `interface_address` | Yes | CIDR | ⚠️ | Rarely changed |
| `description` | No | string | ✅ | Human-readable description |
| `ttl` | No | int | ✅ | Time to live (default: 64) |
| `mtu` | No | int | ✅ | 576-1500 (GRE default: 1476) |
| `health_check.enabled` | No | bool | ✅ | Enable/disable health checks |
| `health_check.rate` | No | string | ✅ | `low` (60s) / `mid` (10s) / `high` (1s) |
| `health_check.target` | No | IP | ✅ | Health check destination |
| `health_check.type` | No | string | ✅ | `request` / `reply` |
| `health_check.direction` | No | string | ✅ | `unidirectional` / `bidirectional` |

**Read-Only Fields (returned but not editable):**

| Field | Description |
|-------|-------------|
| `id` | Tunnel UUID |
| `created_on` | Creation timestamp |
| `modified_on` | Last modification timestamp |
| `bgp_status` | BGP session state |
| `interface_address6` | IPv6 interface (auto-assigned) |

**Health Check Rate Values:**

| Value | Check Interval | Use Case |
|-------|----------------|----------|
| `low` | Every 60 seconds | Stable connections |
| `mid` | Every 10 seconds | Standard (default) |
| `high` | Every 1 second | Critical tunnels |

### 5.5 Delete GRE Tunnel

```http
DELETE /accounts/{account_id}/magic/gre_tunnels/{gre_tunnel_id}
```

### GRE Tunnel Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique tunnel identifier |
| `name` | string | Tunnel name |
| `cloudflare_gre_endpoint` | IP | Cloudflare's GRE endpoint |
| `customer_gre_endpoint` | IP | Customer's GRE endpoint |
| `interface_address` | CIDR | IPv4 interface address |
| `interface_address6` | CIDR | IPv6 interface address (optional) |
| `mtu` | integer | Maximum transmission unit |
| `ttl` | integer | Time to live |
| `bgp_status.state` | string | BGP_UP, BGP_DOWN, etc. |
| `health_check.rate` | string | low, mid, high |

---

## 7. IPsec Tunnels API

### Base URL

```
https://api.cloudflare.com/client/v4/accounts/{account_id}/magic/ipsec_tunnels
```

**Authentication:** API Token (Magic Transit Read/Write)

### 6.1 List IPsec Tunnels

```http
GET /accounts/{account_id}/magic/ipsec_tunnels
```

**Response:**

```json
{
  "success": true,
  "result": {
    "ipsec_tunnels": [
      {
        "id": "string",
        "name": "ipsec-tunnel-1",
        "description": "Primary IPsec tunnel",
        "cloudflare_endpoint": "162.159.X.X",
        "customer_endpoint": "185.54.81.X",
        "interface_address": "10.0.1.1/31",
        "created_on": "2026-01-15T10:00:00Z",
        "modified_on": "2026-01-20T15:30:00Z",
        "replay_protection": false,
        "allow_null_cipher": false,
        "health_check": {
          "enabled": true,
          "type": "reply",
          "rate": "mid",
          "direction": "bidirectional",
          "target": {
            "saved": "10.0.1.1",
            "effective": "10.0.1.1"
          }
        }
      }
    ]
  }
}
```

### 6.2 Get Single IPsec Tunnel

```http
GET /accounts/{account_id}/magic/ipsec_tunnels/{ipsec_tunnel_id}
```

### 6.3 Create IPsec Tunnel

```http
POST /accounts/{account_id}/magic/ipsec_tunnels
```

### 6.4 Update IPsec Tunnel

```http
PUT /accounts/{account_id}/magic/ipsec_tunnels/{ipsec_tunnel_id}
```

**Request Body:**

```json
{
  "name": "ipsec-tunnel-1",
  "cloudflare_endpoint": "162.159.X.X",
  "customer_endpoint": "185.54.81.X",
  "interface_address": "10.0.1.1/31",
  "description": "Updated description",
  "health_check": {
    "enabled": true,
    "target": "185.54.81.X",
    "type": "reply",
    "rate": "mid",
    "direction": "unidirectional"
  }
}
```

**Editable Fields:**

| Field | Required | Type | Editable | Notes |
|-------|:--------:|------|:--------:|-------|
| `name` | Yes | string | ✅ | Tunnel display name |
| `cloudflare_endpoint` | Yes | IP | ❌ | Assigned by Cloudflare |
| `customer_endpoint` | Yes | IP | ✅ | Customer router IP |
| `interface_address` | Yes | CIDR | ⚠️ | Rarely changed |
| `description` | No | string | ✅ | Human-readable description |
| `replay_protection` | No | bool | ✅ | Enable replay protection |
| `allow_null_cipher` | No | bool | ✅ | Allow null cipher (testing) |
| `health_check.enabled` | No | bool | ✅ | Enable/disable health checks |
| `health_check.rate` | No | string | ✅ | `low` / `mid` / `high` |
| `health_check.target` | No | IP | ✅ | Health check destination |
| `health_check.type` | No | string | ✅ | `request` / `reply` |
| `health_check.direction` | No | string | ✅ | `unidirectional` / `bidirectional` |

**Note:** IPsec tunnels don't have `ttl` or `mtu` fields like GRE tunnels. MTU is negotiated during IKE.

### 6.5 Delete IPsec Tunnel

```http
DELETE /accounts/{account_id}/magic/ipsec_tunnels/{ipsec_tunnel_id}
```

### 6.6 Generate Pre-Shared Key (PSK)

```http
POST /accounts/{account_id}/magic/ipsec_tunnels/{ipsec_tunnel_id}/psk_generate
```

**Response:**

```json
{
  "success": true,
  "result": {
    "ipsec_tunnel_id": "string",
    "psk": "generated_psk_value",
    "psk_metadata": {
      "last_generated_on": "2026-01-21T10:00:00Z"
    }
  }
}
```

**Important:** After PSK is generated, it's immediately persisted to Cloudflare's edge and cannot be retrieved later. Store it securely.

### IPsec Tunnel Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique tunnel identifier |
| `name` | string | Tunnel name |
| `cloudflare_endpoint` | IP | Cloudflare's IPsec endpoint |
| `customer_endpoint` | IP | Customer's IPsec endpoint |
| `interface_address` | CIDR | Interface address |
| `replay_protection` | boolean | Enable replay protection |
| `allow_null_cipher` | boolean | Allow null cipher (testing) |
| `health_check.rate` | string | low, mid, high |

---

## 8. Network Interconnects (CNI) API

### Base URLs

```
# Interconnects (physical connections)
https://api.cloudflare.com/client/v4/accounts/{account_id}/cni/interconnects

# CNIs (logical connections on interconnects)
https://api.cloudflare.com/client/v4/accounts/{account_id}/cni/cnis
```

**Authentication:** API Token (Magic Transit/Magic WAN Read/Write)

### 7.1 List Interconnects

```http
GET /accounts/{account_id}/cni/interconnects
```

**Response:**

> ⚠️ **Note:** CNI API response structure differs from other Cloudflare APIs. Data is at `items` (top level), NOT `result.items`.

```json
{
  "items": [
    {
      "name": "dir-1b31917d-0b0c-4fb5-848a-59306935c044",
      "account": "account_id",
      "facility": {
        "name": "Equinix Zurich (ZH4)",
        "address": "Josefstrasse 225, 8005 Zürich"
      },
      "site": "zrh01",
      "speed": "10G",
      "type": "dedicated_nni",
      "slot_id": "string",
      "owner": "customer"
    }
  ],
  "cursor": null
}
```

**Field Notes:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Interconnect identifier (used as ID) |
| `facility` | **object** | Contains `name` and `address` fields |
| `facility.name` | string | Facility display name |
| `facility.address` | string | Physical address |
| `speed` | string | Connection speed (e.g., "10G", "100G") |
| `type` | string | Connection type (`dedicated_nni`, `partner_nni`, etc.) |
```

### 7.2 Get Interconnect Details

```http
GET /accounts/{account_id}/cni/interconnects/{interconnect_id}
```

### 7.3 Get Interconnect Status

```http
GET /accounts/{account_id}/cni/interconnects/{interconnect_id}/status
```

### 7.4 Get LOA (Letter of Authorization)

```http
GET /accounts/{account_id}/cni/interconnects/{interconnect_id}/loa
```

### 7.5 List CNIs

```http
GET /accounts/{account_id}/cni/cnis
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `cursor` | int32 | Pagination cursor |
| `limit` | int | Max results (min: 0) |
| `slot` | string | Filter by slot ID |

**Response:**

> ⚠️ **Note:** CNI API response structure differs from other Cloudflare APIs. Data is at `items` (top level), NOT `result.items`. IP fields are **objects**, not strings.

```json
{
  "items": [
    {
      "id": "cni_abc123",
      "account": "account_id",
      "interconnect": "dir-1b31917d-0b0c-4fb5-848a-59306935c044",
      "p2p_ip": {
        "ip": "169.254.66.30",
        "cidr": 31
      },
      "cust_ip": {
        "ip": "169.254.66.31",
        "cidr": 31
      },
      "magic": {
        "conduit_name": "ZRH-CNI",
        "description": "CNI_GOLINE_ZH",
        "mtu": 1500
      },
      "bgp": {
        "customer_asn": 202032,
        "md5_key": "optional_secret",
        "extra_prefixes": ["185.54.80.0/22"]
      }
    }
  ],
  "cursor": null
}
```

**Field Notes - IP Address Objects:**

| Field | Type | Description |
|-------|------|-------------|
| `p2p_ip` | **object** | Cloudflare P2P IP (NOT a string) |
| `p2p_ip.ip` | string | IP address without mask |
| `p2p_ip.cidr` | integer | CIDR prefix length |
| `cust_ip` | **object** | Customer P2P IP (NOT a string) |
| `cust_ip.ip` | string | IP address without mask |
| `cust_ip.cidr` | integer | CIDR prefix length |

**Parsing Example (Python):**

```python
# Correct parsing for p2p_ip and cust_ip
p2p_ip_obj = item.get('p2p_ip', {})
cust_ip_obj = item.get('cust_ip', {})

p2p_cloudflare = f"{p2p_ip_obj.get('ip')}/{p2p_ip_obj.get('cidr')}"  # "169.254.66.30/31"
p2p_customer = f"{cust_ip_obj.get('ip')}/{cust_ip_obj.get('cidr')}"  # "169.254.66.31/31"
```
```

### 7.6 Get CNI Details

```http
GET /accounts/{account_id}/cni/cnis/{cni_id}
```

### 7.7 Create CNI

```http
POST /accounts/{account_id}/cni/cnis
```

**Request Body:**

```json
{
  "interconnect": "interconnect_id",
  "p2p_ip": "169.254.100.0/31",
  "cust_ip": "169.254.100.1/31",
  "magic": {
    "conduit_name": "my-cni",
    "description": "Production CNI",
    "mtu": 1500
  },
  "bgp": {
    "customer_asn": 202032
  }
}
```

### 7.8 Update CNI

```http
PATCH /accounts/{account_id}/cni/cnis/{cni_id}
```

**Request Body (partial update supported):**

```json
{
  "magic": {
    "description": "Updated CNI description",
    "mtu": 1500
  }
}
```

**Editable Fields:**

| Field | Type | Editable | Notes |
|-------|------|:--------:|-------|
| `magic.description` | string | ✅ | Human-readable description |
| `magic.mtu` | int | ✅ | MTU (default: 1500) |
| `magic.conduit_name` | string | ⚠️ | May affect routing |
| `bgp.customer_asn` | int | ⚠️ | Changes BGP peering |
| `bgp.md5_key` | string | ✅ | BGP MD5 authentication |
| `p2p_ip` | object | ❌ | Assigned by Cloudflare |
| `cust_ip` | object | ❌ | Assigned by Cloudflare |
| `interconnect` | string | ❌ | Parent interconnect |

**Response:** Returns updated CNI object on success (not wrapped in `result`).

### 7.9 Delete CNI

```http
DELETE /accounts/{account_id}/cni/cnis/{cni_id}
```

### CNI Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique CNI identifier |
| `interconnect` | string | Parent interconnect ID (matches interconnect `name`) |
| `p2p_ip` | **object** | Cloudflare P2P IP object |
| `p2p_ip.ip` | string | IP address (e.g., "169.254.66.30") |
| `p2p_ip.cidr` | integer | CIDR prefix (e.g., 31) |
| `cust_ip` | **object** | Customer P2P IP object |
| `cust_ip.ip` | string | IP address (e.g., "169.254.66.31") |
| `cust_ip.cidr` | integer | CIDR prefix (e.g., 31) |
| `magic.conduit_name` | string | Magic Transit conduit name |
| `magic.description` | string | Human-readable description |
| `magic.mtu` | integer | MTU (default 1500) |
| `bgp.customer_asn` | integer | Customer ASN for BGP peering |

### API Response Structure Differences

> ⚠️ **Important:** The CNI API uses a different response structure than other Cloudflare APIs:

| Standard Cloudflare API | CNI API |
|-------------------------|---------|
| `result.items` | `items` (top level) |
| `result.next` | `cursor` (top level) |
| IP fields as strings | IP fields as objects with `ip` + `cidr` |
| `facility` as string | `facility` as object with `name` + `address` |

### CNI Partners

Cloudflare partners for interconnects:

| Partner | Type |
|---------|------|
| Console Connect | Virtual |
| CoreSite | Physical |
| Digital Realty | Physical |
| Equinix Fabric | Virtual |
| Megaport | Virtual |
| PacketFabric | Virtual |
| Zayo | Physical |

---

## 9. Tunnel Health Check GraphQL

### Endpoint

```
POST https://api.cloudflare.com/client/v4/graphql
```

### Query: Tunnel Health Check Results

**Used by:** `dashboard/app.py` (Connectors page)

```graphql
query GetTunnelHealth($accountTag: String!, $since: Time!, $until: Time!) {
    viewer {
        accounts(filter: {accountTag: $accountTag}) {
            magicTransitTunnelHealthChecksAdaptiveGroups(
                limit: 100,
                filter: {
                    datetime_geq: $since,
                    datetime_lt: $until
                }
            ) {
                avg {
                    tunnelState
                }
                dimensions {
                    tunnelName
                    edgeColoName
                }
            }
        }
    }
}
```

**Variables:**

| Variable | Type | Example |
|----------|------|---------|
| `accountTag` | String | `"YOUR_ACCOUNT_ID"` |
| `since` | Time | `"2026-01-21T09:00:00Z"` |
| `until` | Time | `"2026-01-21T10:00:00Z"` |

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `tunnelState` | float | Health state: 0 = down, 0.5 = degraded, 1 = healthy |
| `tunnelName` | string | Tunnel identifier |
| `edgeColoName` | string | Cloudflare datacenter name |

### Health State Interpretation

| Value | Status | Description |
|-------|--------|-------------|
| 1.0 | Healthy | >80% health checks passing |
| 0.5 | Degraded | 40-80% health checks passing |
| 0.0 | Down | <40% health checks passing |

### Notes

- Health check data aggregated from Cloudflare servers to GRE/IPsec/CNI endpoints
- Query up to 1 week of data for dates up to 3 months ago
- For real-time data, use 1-hour lookback window

---

## 10. Telegram Bot API

All scripts use Telegram for real-time notifications.

### Endpoint

```
POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage
```

### Request Body

```json
{
  "chat_id": "YOUR_TELEGRAM_CHAT_ID",
  "text": "🛡️ *CLOUDFLARE DDoS PROTECTION*\n\n📊 Message content...",
  "parse_mode": "Markdown",
  "disable_web_page_preview": true
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `chat_id` | string | Yes | Telegram chat/group ID |
| `text` | string | Yes | Message text (max 4096 chars) |
| `parse_mode` | string | No | `Markdown` or `HTML` |
| `disable_web_page_preview` | boolean | No | Disable link previews |

### Response

```json
{
  "ok": true,
  "result": {
    "message_id": 12345,
    "from": {"id": 123456789, "is_bot": true},
    "chat": {"id": YOUR_TELEGRAM_CHAT_ID},
    "date": 1737456000,
    "text": "..."
  }
}
```

### Error Response

```json
{
  "ok": false,
  "error_code": 400,
  "description": "Bad Request: can't parse entities"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid Markdown/HTML syntax |
| 401 | Invalid bot token |
| 403 | Bot blocked by user/group |
| 429 | Rate limited (wait and retry) |

---

## Wirefilter Expression Syntax

Cloudflare uses **Wirefilter** syntax for custom expressions in DDoS overrides. This is the same syntax used in Firewall Rules and other Cloudflare products.

### Basic Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `ip.dst eq 185.54.81.15` |
| `ne` | Not equals | `ip.proto.num ne 6` |
| `in` | In set | `tcp.dstport in {80 443 8080}` |
| `gt` | Greater than | `tcp.dstport gt 1024` |
| `ge` | Greater or equal | `tcp.dstport ge 1024` |
| `lt` | Less than | `tcp.dstport lt 1024` |
| `le` | Less or equal | `tcp.dstport le 1024` |

### Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `and` | Logical AND | `ip.dst eq X and tcp.dstport eq 80` |
| `or` | Logical OR | `tcp.dstport eq 80 or tcp.dstport eq 443` |
| `not` | Logical NOT | `not ip.dst eq X` |

### Available Fields (L3/L4)

#### IP Fields

| Field | Type | Description |
|-------|------|-------------|
| `ip.dst` | IP address | Destination IP |
| `ip.src` | IP address | Source IP |
| `ip.proto.num` | Integer | IP protocol number |

#### Protocol Numbers

| Number | Protocol |
|--------|----------|
| 1 | ICMP |
| 6 | TCP |
| 17 | UDP |
| 47 | GRE |
| 50 | ESP (IPsec) |
| 51 | AH (IPsec) |

#### TCP Fields

| Field | Type | Description |
|-------|------|-------------|
| `tcp.dstport` | Integer | Destination port |
| `tcp.srcport` | Integer | Source port |

#### UDP Fields

| Field | Type | Description |
|-------|------|-------------|
| `udp.dstport` | Integer | Destination port |
| `udp.srcport` | Integer | Source port |

### Expression Examples

#### Single IP, All Traffic

```
ip.dst eq 185.54.81.15
```

#### Single IP, Specific TCP Ports

```
ip.dst eq 185.54.81.15 and tcp.dstport in {80 443}
```

#### Single IP, Port Range

```
ip.dst eq 185.54.81.15 and tcp.dstport ge 8000 and tcp.dstport le 9000
```

#### Single IP, Specific Protocol (ESP/IPsec)

```
ip.dst eq 185.54.80.30 and ip.proto.num eq 50
```

#### Single IP, UDP DNS

```
ip.dst eq 185.54.81.53 and udp.dstport eq 53
```

#### Single IP, All TCP Traffic

```
ip.dst eq 185.54.81.15 and ip.proto.num eq 6
```

#### Single IP, All UDP Traffic

```
ip.dst eq 185.54.81.15 and ip.proto.num eq 17
```

#### Multiple IPs

```
ip.dst in {185.54.81.15 185.54.81.16 185.54.81.17}
```

#### IP Range (CIDR not supported - use multiple IPs)

```
ip.dst in {185.54.81.1 185.54.81.2 185.54.81.3 185.54.81.4}
```

### Common Service Expressions

| Service | Expression |
|---------|------------|
| Web Server | `ip.dst eq X and tcp.dstport in {80 443}` |
| Mail Server | `ip.dst eq X and tcp.dstport in {25 110 143 465 587 993 995}` |
| DNS | `ip.dst eq X and udp.dstport eq 53` |
| SSH | `ip.dst eq X and tcp.dstport eq 22` |
| RDP | `ip.dst eq X and tcp.dstport eq 3389` |
| IPSec ESP | `ip.dst eq X and ip.proto.num eq 50` |
| WireGuard | `ip.dst eq X and udp.dstport eq 51820` |
| MySQL | `ip.dst eq X and tcp.dstport eq 3306` |
| PostgreSQL | `ip.dst eq X and tcp.dstport eq 5432` |
| Redis | `ip.dst eq X and tcp.dstport eq 6379` |
| Elasticsearch | `ip.dst eq X and tcp.dstport in {9200 9300}` |
| SNMP | `ip.dst eq X and udp.dstport in {161 162}` |
| NTP | `ip.dst eq X and udp.dstport eq 123` |
| Syslog | `ip.dst eq X and udp.dstport eq 514` |
| BGP | `ip.dst eq X and tcp.dstport eq 179` |
| Kubernetes API | `ip.dst eq X and tcp.dstport eq 6443` |
| Docker Registry | `ip.dst eq X and tcp.dstport eq 5000` |
| Veeam Backup | `ip.dst eq X and tcp.dstport in {6160 6162 9401}` |
| iSCSI | `ip.dst eq X and tcp.dstport eq 3260` |
| Modbus | `ip.dst eq X and tcp.dstport eq 502` |
| BACnet | `ip.dst eq X and udp.dstport eq 47808` |

### Expression Validation

Expressions are validated when creating or updating rules. Invalid expressions return errors:

**Invalid field:**
```json
{
  "success": false,
  "errors": [
    {
      "code": 6003,
      "message": "could not parse expression: unknown field 'ip.invalid'"
    }
  ]
}
```

**Syntax error:**
```json
{
  "success": false,
  "errors": [
    {
      "code": 6003,
      "message": "could not parse expression: expected 'and' or 'or' at position 25"
    }
  ]
}
```

### Limitations

- **No CIDR notation** - Use `in {ip1 ip2 ip3}` for multiple IPs
- **No wildcards** - Must specify exact values
- **No regex** - Use exact matches or sets
- **Port ranges** - Use `ge`/`le` operators, not `X-Y` notation
- **Max expression length** - 4096 characters

---

## Rate Limits

| API | Limit |
|-----|-------|
| GraphQL | 300 req/5min |
| BGP Prefixes GET | 1200 req/min |
| BGP Prefixes PATCH | 60 changes/hour |
| MNM Rules | 1200 req/5min |
| DDoS Rulesets GET | 1200 req/5min |
| DDoS Rulesets PUT | 60 req/5min |

---

## Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Rate Limited / Constraint Violation |
| 500 | Internal Server Error |

### Cloudflare Error Codes

| Code | Message | API |
|------|---------|-----|
| 1001 | Invalid request body | All |
| 1002 | 15-minute constraint violation | BGP Prefixes |
| 1003 | Permission denied | All |
| 1004 | Resource not found | All |
| 10006 | Invalid action for rule | DDoS Rules |
| 10007 | Invalid sensitivity level | DDoS Rules |

---

## Scripts Using These APIs

| Script | APIs Used |
|--------|-----------|
| `cloudflare-network-analytics-monitor.py` | GraphQL (dosd), BGP Prefixes (GET), Telegram |
| `cloudflare-autowithdraw.py` | GraphQL (magicTransit), BGP Prefixes, Telegram |
| `cloudflare-prefix-manager.py` | BGP Prefixes, Telegram |
| `cloudflare-rules-manager.py` | MNM Rules, DDoS Rulesets |
| `cloudflare-webhook-receiver.py` | Telegram |
| `cloudflare-services-watchdog.sh` | Telegram |
| `dashboard/app.py` | All Cloudflare APIs including Connectors |

### Dashboard Connectors Page APIs

| Endpoint | APIs Used |
|----------|-----------|
| `/api/connectors/tunnels` | GRE Tunnels, IPsec Tunnels |
| `/api/connectors/interconnects` | CNI Interconnects, CNIs |
| `/api/connectors/tunnel-health` | GraphQL (Tunnel Health Checks) |

---

## References

### Cloudflare Documentation

- [Cloudflare GraphQL Analytics](https://developers.cloudflare.com/analytics/graphql-api/)
- [Magic Transit Prefix Management](https://developers.cloudflare.com/magic-transit/how-to/advertise-prefixes/)
- [MNM Rules](https://developers.cloudflare.com/magic-network-monitoring/)
- [DDoS Protection - Managed Rulesets](https://developers.cloudflare.com/ddos-protection/managed-rulesets/network/)
- [DDoS Protection - Override Settings](https://developers.cloudflare.com/ddos-protection/managed-rulesets/network/override-settings/)
- [Ruleset Engine - Update Rule](https://developers.cloudflare.com/ruleset-engine/rulesets-api/update-rule/)
- [Ruleset Engine - Add Rule](https://developers.cloudflare.com/ruleset-engine/rulesets-api/add-rule/)
- [Wirefilter Syntax](https://developers.cloudflare.com/ruleset-engine/rules-language/)
- [GRE/IPsec Tunnels](https://developers.cloudflare.com/magic-transit/reference/gre-ipsec-tunnels/)
- [Network Interconnect](https://developers.cloudflare.com/network-interconnect/)
- [Tunnel Health Checks](https://developers.cloudflare.com/magic-transit/reference/tunnel-health-checks/)
- [Tunnel Health GraphQL](https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-magic-transit-tunnel-healthcheck-results/)

### External APIs

- [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage)

### GOLINE Internal

- Dashboard: `https://cloudflare.goline.ch`
- Webhook: `https://lg.goline.ch/webhook/cloudflare`
- Health Check: `https://lg.goline.ch/mt-health`

---

*GOLINE SOC - Cloudflare Magic Transit Integration v2.0.0*
