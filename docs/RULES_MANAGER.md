# Cloudflare MNM Rules Manager

**Script**: `cloudflare-rules-manager.py`
**Version**: 1.4
**Last Updated**: 2026-01-22

---

## Overview

Interactive CLI tool for managing **Magic Network Monitoring (MNM)** rules. These rules control when Cloudflare automatically advertises BGP prefixes in response to DDoS attacks.

### What are MNM Rules?

MNM rules define thresholds that trigger automatic BGP advertisement:
- **BPS (Bandwidth)**: Triggers when traffic exceeds X Gbps
- **PPS (Packets)**: Triggers when packets exceed X pps
- **ZScore (Dynamic)**: Triggers on anomaly detection based on traffic baseline
- **Advanced DDoS (sFlow)**: Triggers on fingerprint-based attack patterns using sFlow sampling

When a rule triggers, Cloudflare automatically:
1. Announces the BGP prefix via Magic Transit
2. Routes traffic through Cloudflare's scrubbing centers
3. Sends webhook notification (`fbm_auto_advertisement`)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MNM RULES TRIGGER FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Normal Traffic                                                              │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐                                                             │
│  │ MNM Monitor │ ← Cloudflare monitors all traffic to your prefixes         │
│  └──────┬──────┘                                                             │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  Rule Evaluation (every minute)                                  │        │
│  │                                                                  │        │
│  │  BPS Rule: Traffic > 4 Gbps for 1 minute?                       │        │
│  │  PPS Rule: Packets > 500k pps for 1 minute?                     │        │
│  │  ZScore: Anomaly detected (deviation from baseline)?            │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         │                                                                    │
│         │ Rule triggered                                                     │
│         ▼                                                                    │
│  ┌─────────────┐                                                             │
│  │ Auto-Advert │ ← Cloudflare announces BGP prefix                          │
│  └──────┬──────┘                                                             │
│         │                                                                    │
│         ├──► Webhook notification (fbm_auto_advertisement)                   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────┐                                                             │
│  │ DDoS Scrub  │ ← Traffic routed through Cloudflare                        │
│  └─────────────┘                                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Authentication

### Global API Key (Required)

This script uses the **Global API Key** authentication method, which is different from the API Token used by other scripts in this project.

| Method | Header Format | Permissions |
|--------|---------------|-------------|
| **API Token** | `Authorization: Bearer <token>` | Scoped (limited) |
| **Global API Key** | `X-Auth-Email` + `X-Auth-Key` | **Full account access** |

**Why Global API Key?**

The MNM Rules API requires full account permissions that may not be available with scoped API Tokens. The Global API Key provides unrestricted access to all account resources.

### Credentials Used

```python
ACCOUNT_ID = "YOUR_ACCOUNT_ID"
AUTH_EMAIL = "YOUR_EMAIL"
AUTH_KEY = "YOUR_GLOBAL_API_KEY"
```

### API Headers

```python
HEADERS = {
    "X-Auth-Email": AUTH_EMAIL,    # Account email
    "X-Auth-Key": AUTH_KEY,        # Global API Key
    "Content-Type": "application/json"
}
```

**Security Note**: The Global API Key has full account access. Never expose it in public repositories or logs.

---

## Usage

### Launch Interactive Menu

```bash
python3 /root/Cloudflare_MT_Integration/scripts/cloudflare-rules-manager.py
```

### Main Menu

```
┌────────────────────────────────────────────────────────┐
│   CLOUDFLARE MAGIC NETWORK MONITORING MANAGER          │
│   GOLINE SA - SOC Tools v1.4                           │
├────────────────────────────────────────────────────────┤
│  MNM RULES                                             │
│   [1] List all rules                                   │
│   [2] List dynamic rules (zscore)                      │
│   [3] List threshold rules (BPS/PPS)                   │
│   [4] List advanced DDoS rules (sFlow)                 │
│   [5] General status                                   │
├────────────────────────────────────────────────────────┤
│  ADD RULES                                             │
│   [6] Add BPS rule (bandwidth)                         │
│   [7] Add PPS rule (packets)                           │
│   [8] Add dynamic rule (zscore)                        │
│   [9] Add advanced DDoS rule (sFlow fingerprint)       │
├────────────────────────────────────────────────────────┤
│  DELETE RULES                                          │
│   [d] Delete single rule                               │
│   [t] Delete rules by type                             │
├────────────────────────────────────────────────────────┤
│  DDOS SENSITIVITY (L3/4 Managed Ruleset)               │
│   [s] DDoS protection status                           │
│   [l] List customizable DDoS rules                     │
│   [m] Modify rule sensitivity/action                   │
│   [o] View current overrides                           │
├────────────────────────────────────────────────────────┤
│  OTHER                                                 │
│   [e] Export configuration (JSON)                      │
│   [q] Quit                                             │
└────────────────────────────────────────────────────────┘
```

---

## Rule Types

### BPS Rules (Bandwidth Threshold)

Triggers when bandwidth exceeds threshold for specified duration.

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Prefix** | Target prefix (e.g., 185.54.81.0/24) | - |
| **Threshold** | Bandwidth in Gbps | 2 Gbps |
| **Duration** | Time traffic must exceed threshold | 1 minute |
| **Auto-Advertisement** | Automatically announce BGP | Yes |

**Example**: "If traffic to 185.54.81.0/24 exceeds 4 Gbps for 1 minute, advertise prefix"

### PPS Rules (Packet Threshold)

Triggers when packet rate exceeds threshold for specified duration.

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Prefix** | Target prefix | - |
| **Threshold** | Packets per second (kpps) | 500 kpps |
| **Duration** | Time packets must exceed threshold | 1 minute |
| **Auto-Advertisement** | Automatically announce BGP | Yes |

**Example**: "If packets to 185.54.82.0/24 exceed 500k pps for 1 minute, advertise prefix"

### ZScore Rules (Dynamic/Anomaly)

Triggers on statistical anomaly compared to baseline traffic.

| Parameter | Description | Options |
|-----------|-------------|---------|
| **Prefix** | Target prefix | - |
| **Sensitivity** | Detection sensitivity | low, medium, high |
| **Target** | What to monitor | bits, packets |
| **Auto-Advertisement** | Automatically announce BGP | Yes |

**Sensitivity Levels**:
- **Low**: Less sensitive, fewer false positives
- **Medium**: Balanced (recommended)
- **High**: More sensitive, more false positives

**Note**: ZScore rules were removed from GOLINE due to false positives during backup operations.

### Advanced DDoS Rules (sFlow Fingerprint)

Triggers on fingerprint-based attack patterns detected through sFlow sampling. Unlike threshold-based rules, these detect specific DDoS attack signatures regardless of traffic volume.

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Prefix** | Target prefix | - |
| **Prefix Match** | `subnet` (any IP in prefix) or `exact` | subnet |
| **Duration** | Time before auto-advertisement | 1 minute |
| **Auto-Advertisement** | Automatically announce BGP | Yes |

**How it works**:
- Cloudflare analyzes sFlow samples for known DDoS attack fingerprints
- Detects attack patterns like SYN floods, UDP amplification, etc.
- Can trigger even if traffic doesn't exceed volume thresholds
- Complements BPS/PPS rules for comprehensive protection

**Example**: "If sFlow detects a DDoS attack fingerprint targeting 185.54.81.0/24, advertise prefix"

---

## Rule Generation Details

### Static Rules (BPS/PPS) - Threshold-Based

Static rules use fixed thresholds and are evaluated every minute by Cloudflare's monitoring system.

#### BPS Rule API Payload

```json
{
    "name": "DDoS Protection BPS 185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "bandwidth_threshold": 4000000000,
    "automatic_advertisement": true,
    "duration": "1m0s"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Rule name (convention: `DDoS Protection BPS {prefix}`) |
| `prefixes` | array | List of prefixes to monitor (usually one per rule) |
| `bandwidth_threshold` | integer | Threshold in **bits per second** (not Gbps!) |
| `automatic_advertisement` | boolean | Auto-advertise BGP when triggered |
| `duration` | string | Time traffic must exceed threshold (format: `Xm0s`) |

**Threshold Conversion**:
- 1 Gbps = 1,000,000,000 bps
- 4 Gbps = 4,000,000,000 bps
- Script uses: `threshold_bps = int(float(threshold_gbps) * 1_000_000_000)`

#### PPS Rule API Payload

```json
{
    "name": "DDoS Protection PPS 185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "packet_threshold": 500000,
    "automatic_advertisement": true,
    "duration": "1m0s"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Rule name (convention: `DDoS Protection PPS {prefix}`) |
| `prefixes` | array | List of prefixes to monitor |
| `packet_threshold` | integer | Threshold in **packets per second** |
| `automatic_advertisement` | boolean | Auto-advertise BGP when triggered |
| `duration` | string | Time packets must exceed threshold |

**Threshold Conversion**:
- 500 kpps = 500,000 pps
- Script uses: `threshold_pps = int(float(threshold_kpps) * 1_000)`

### Dynamic Rules (ZScore) - sFlow-Based Anomaly Detection

Dynamic rules use **sFlow sampling** and statistical analysis to detect traffic anomalies compared to a learned baseline.

#### ZScore Rule API Payload

```json
{
    "name": "Dynamic DDoS Detection 185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "automatic_advertisement": true,
    "type": "zscore",
    "zscore_sensitivity": "medium",
    "zscore_target": "bits",
    "duration": "1m"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Rule name (convention: `Dynamic DDoS Detection {prefix}`) |
| `prefixes` | array | List of prefixes to monitor |
| `type` | string | Must be `"zscore"` for dynamic rules |
| `zscore_sensitivity` | string | `"low"`, `"medium"`, or `"high"` |
| `zscore_target` | string | `"bits"` (bandwidth) or `"packets"` (packet rate) |
| `automatic_advertisement` | boolean | Auto-advertise BGP when triggered |
| `duration` | string | Observation window |

#### How ZScore Detection Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ZSCORE ANOMALY DETECTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. BASELINE LEARNING (continuous)                                           │
│     └─► Cloudflare collects sFlow samples from your traffic                 │
│     └─► Builds statistical model: mean (μ) and std deviation (σ)            │
│                                                                              │
│  2. REAL-TIME MONITORING                                                     │
│     └─► Every minute: calculate current traffic Z-Score                      │
│                                                                              │
│         Z-Score = (current_traffic - mean) / std_deviation                   │
│                                                                              │
│  3. ANOMALY DETECTION                                                        │
│                                                                              │
│     Sensitivity  │  Z-Score Threshold  │  False Positive Risk               │
│     ─────────────┼─────────────────────┼────────────────────                 │
│     low          │  ~3.5σ              │  Low                                │
│     medium       │  ~3.0σ              │  Medium (recommended)               │
│     high         │  ~2.5σ              │  High                               │
│                                                                              │
│  4. TRIGGER                                                                  │
│     └─► If Z-Score exceeds threshold → Auto-advertise prefix                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### sFlow Data Source

ZScore rules rely on **sFlow** (sampled flow data) collected by Cloudflare:
- Cloudflare samples traffic to your prefixes at network edge
- Samples are aggregated to build traffic profiles
- Statistical analysis detects deviations from normal patterns

**Advantages of ZScore**:
- Adapts to traffic patterns automatically
- Can detect attacks that don't exceed fixed thresholds
- Good for variable traffic environments

**Disadvantages**:
- Can trigger on legitimate traffic spikes (backups, software updates)
- Requires stable baseline (not good for new prefixes)
- More complex to tune than static rules

#### Why GOLINE Removed ZScore Rules

ZScore rules were disabled due to:
1. **Backup Operations**: Nightly backups caused traffic spikes that triggered false positives
2. **Traffic Variability**: GOLINE's traffic patterns vary significantly by time of day
3. **Static Rules Sufficient**: BPS/PPS rules provide adequate protection without false positives

### Advanced DDoS Rules (sFlow Fingerprint) - Pattern-Based Detection

Advanced DDoS rules use fingerprint-based detection through sFlow sampling to identify specific DDoS attack patterns.

#### Advanced DDoS Rule API Payload

```json
{
    "name": "sFlow-DDoS-Attack-185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "type": "advanced_ddos",
    "prefix_match": "subnet",
    "automatic_advertisement": true,
    "duration": "1m0s"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Rule name (convention: `sFlow-DDoS-Attack-{prefix}`) |
| `prefixes` | array | List of prefixes to monitor |
| `type` | string | Must be `"advanced_ddos"` for fingerprint-based rules |
| `prefix_match` | string | `"subnet"` (matches any IP in prefix) or `"exact"` |
| `automatic_advertisement` | boolean | Auto-advertise BGP when triggered |
| `duration` | string | Time before triggering (format: `Xm0s`) |

#### Prefix Match Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `subnet` | Matches traffic to any IP within the prefix | Recommended for most deployments |
| `exact` | Matches only traffic destined to the exact prefix | Specific use cases only |

#### How Advanced DDoS Detection Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ADVANCED DDOS (sFlow Fingerprint) DETECTION               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. sFlow SAMPLING (continuous)                                              │
│     └─► Cloudflare collects sFlow samples from network edges                │
│     └─► Analyzes packet headers, protocols, flags, payloads                 │
│                                                                              │
│  2. FINGERPRINT MATCHING                                                     │
│     └─► Compares traffic patterns against known DDoS signatures             │
│                                                                              │
│     Attack Type         │  Fingerprint Characteristics                      │
│     ────────────────────┼────────────────────────────────                   │
│     SYN Flood           │  High SYN packets, no ACK responses               │
│     UDP Amplification   │  Large UDP packets, specific ports (DNS, NTP)     │
│     ICMP Flood          │  High ICMP echo request volume                    │
│     TCP ACK Flood       │  High ACK packets without established sessions    │
│     DNS Amplification   │  Large DNS responses, ANY queries                 │
│                                                                              │
│  3. TRIGGER                                                                  │
│     └─► If fingerprint matches known attack → Auto-advertise prefix         │
│                                                                              │
│  ADVANTAGE: Can detect attacks that don't exceed volume thresholds          │
│  ADVANTAGE: Pattern-based detection catches sophisticated attacks           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### When to Use Advanced DDoS Rules

| Use Case | Recommended |
|----------|-------------|
| **Small volumetric attacks** | Yes - detects patterns even with low volume |
| **Sophisticated attacks** | Yes - fingerprint matching catches complex patterns |
| **Complement to BPS/PPS** | Yes - provides additional detection layer |
| **All prefixes** | Recommended to enable on all protected prefixes |

---

## Current Configuration (GOLINE)

### Active Rules (12 total)

| Prefix | Rule Type | Threshold | Duration | Auto-Adv |
|--------|-----------|-----------|----------|----------|
| 185.54.80.0/24 | BPS | 4 Gbps | 1 min | ✅ |
| 185.54.80.0/24 | PPS | 500k pps | 1 min | ✅ |
| 185.54.81.0/24 | BPS | 4 Gbps | 1 min | ✅ |
| 185.54.81.0/24 | PPS | 500k pps | 1 min | ✅ |
| 185.54.82.0/24 | BPS | 4 Gbps | 1 min | ✅ |
| 185.54.82.0/24 | PPS | 500k pps | 1 min | ✅ |
| 185.54.83.0/24 | BPS | 4 Gbps | 1 min | ✅ |
| 185.54.83.0/24 | PPS | 500k pps | 1 min | ✅ |
| 2a02:4460:1::/48 | BPS | 4 Gbps | 1 min | ✅ |
| 2a02:4460:1::/48 | PPS | 500k pps | 1 min | ✅ |
| All IPv4 prefixes | Advanced DDoS | Fingerprint | 1 min | ✅ |
| 2a02:4460:1::/48 | Advanced DDoS | Fingerprint | 1 min | ✅ |

**Notes**:
- IPv6 prefix `2a02:4460:1::/48` added on 2026-01-20 (was locked, now manageable)
- Advanced DDoS (sFlow) rules added on 2026-01-20 for fingerprint-based detection

### Why These Thresholds?

| Threshold | Reasoning |
|-----------|-----------|
| **4 Gbps** | Well above normal traffic (~100-500 Mbps), catches volumetric attacks |
| **500k pps** | Catches packet floods that may not show high bandwidth |
| **1 minute** | Quick response while avoiding false triggers from traffic spikes |

---

## Operations

### Adding a BPS Rule

```
Select option: 5

ADD BPS RULE (Bandwidth)

Available prefixes:
  [1] 185.54.80.0/24
  [2] 185.54.81.0/24
  [3] 185.54.82.0/24
  [4] 185.54.83.0/24
  [5] Enter manually

Select prefix [1-5]: 2
Threshold in Gbps [default: 2]: 4
Duration in minutes [default: 1]: 1
Auto-advertisement? [Y/n]: Y

Creating rule: DDoS Protection BPS 185.54.81.0-24
  Threshold: 4 Gbps
  Duration: 1 min
  Auto-Adv: True

Confirm? [Y/n]: Y
✅ Rule created! ID: abc123def456
```

### Adding a PPS Rule

```
Select option: 6

ADD PPS RULE (Packets)

Available prefixes:
  [1] 185.54.80.0/24
  ...

Select prefix [1-5]: 2
Threshold in kpps [default: 500]: 500
Duration in minutes [default: 1]: 1
Auto-advertisement? [Y/n]: Y

Creating rule: DDoS Protection PPS 185.54.81.0-24
  Threshold: 500 kpps
  Duration: 1 min
  Auto-Adv: True

Confirm? [Y/n]: Y
✅ Rule created! ID: xyz789abc012
```

### Adding an Advanced DDoS Rule

```
Select option: 9

ADD ADVANCED DDOS RULE (sFlow Fingerprint)

This creates a fingerprint-based DDoS detection rule using sFlow.
These rules detect attack patterns regardless of traffic volume.

Available prefixes:
  [1] 185.54.80.0/24
  [2] 185.54.81.0/24
  [3] 185.54.82.0/24
  [4] 185.54.83.0/24
  [5] 2a02:4460:1::/48
  [6] All IPv4 prefixes (4 rules)
  [7] All prefixes including IPv6 (5 rules)
  [8] Enter manually

Select prefix [1-8]: 7

Prefix match mode:
  [1] subnet - Matches traffic to any IP in the prefix (recommended)
  [2] exact - Matches only traffic to the exact prefix

Select [1-2, default: 1]: 1
Duration in minutes [default: 1]: 1
Auto-advertisement? [Y/n]: Y

Creating 5 advanced DDoS rules:
  Type: advanced_ddos (sFlow fingerprint)
  Prefix match: subnet
  Duration: 1 min
  Auto-Adv: True

Prefixes:
  - 185.54.80.0/24
  - 185.54.81.0/24
  - 185.54.82.0/24
  - 185.54.83.0/24
  - 2a02:4460:1::/48

Confirm? [Y/n]: Y
✅ Created: sFlow-DDoS-Attack-185.54.80.0-24 (ID: abc123def456...)
✅ Created: sFlow-DDoS-Attack-185.54.81.0-24 (ID: def456abc789...)
✅ Created: sFlow-DDoS-Attack-185.54.82.0-24 (ID: ghi789def012...)
✅ Created: sFlow-DDoS-Attack-185.54.83.0-24 (ID: jkl012ghi345...)
✅ Created: sFlow-DDoS-Attack-IPv6 (ID: mno345jkl678...)

Created 5/5 advanced DDoS rules.
```

### Deleting Rules

**Single Rule** (option d):
```
Select rule to delete [1-8] or 'q' to cancel: 3

You are about to delete: DDoS Protection BPS 185.54.82.0-24
  ID: abc123
  Prefixes: 185.54.82.0/24

Are you sure? Type 'DELETE' to confirm: DELETE
✅ Rule deleted!
```

**By Type** (option t):
```
Select type of rules to delete:
  [1] Threshold BPS (5 rules)
  [2] Threshold PPS (5 rules)
  [3] Dynamic/ZScore (0 rules)
  [4] Advanced DDoS/sFlow (2 rules)
  [5] ALL (12 rules)

Select [1-5] or 'q' to cancel: 4

You are about to delete 2 rules:
  - sFlow-DDoS-Attack-IPv4
  - sFlow-DDoS-Attack-IPv6

Are you sure? Type 'DELETE ALL' to confirm: DELETE ALL
✅ Deleted: sFlow-DDoS-Attack-IPv4
✅ Deleted: sFlow-DDoS-Attack-IPv6

Deleted 2/2 rules.
```

### Exporting Configuration

```
Select option: e

✅ Configuration exported to: mnm_rules_backup_20260119_143000.json
```

Creates a JSON file with all rules for backup/documentation.

---

## API Reference

### Cloudflare MNM Rules API

**Endpoint**: `https://api.cloudflare.com/client/v4/accounts/{account_id}/mnm/rules`

### List Rules

```bash
curl -X GET "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" \
  -H "Content-Type: application/json"
```

### Create BPS Rule

```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DDoS Protection BPS 185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "bandwidth_threshold": 4000000000,
    "automatic_advertisement": true,
    "duration": "1m0s"
  }'
```

### Create PPS Rule

```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DDoS Protection PPS 185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "packet_threshold": 500000,
    "automatic_advertisement": true,
    "duration": "1m0s"
  }'
```

### Create Advanced DDoS Rule

```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sFlow-DDoS-Attack-185.54.81.0-24",
    "prefixes": ["185.54.81.0/24"],
    "type": "advanced_ddos",
    "prefix_match": "subnet",
    "automatic_advertisement": true,
    "duration": "1m0s"
  }'
```

### Delete Rule

```bash
curl -X DELETE "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules/${RULE_ID}" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}"
```

---

## DDoS Sensitivity Management (v1.4)

The script now includes full management of the **Cloudflare L3/4 DDoS Managed Ruleset**, which contains 124+ fingerprint-based attack detection rules used by the sFlow analysis engine.

### What is the DDoS Managed Ruleset?

The L3/4 DDoS Managed Ruleset is a collection of Cloudflare-maintained rules that detect DDoS attack patterns:

| Category | Description | Rules |
|----------|-------------|-------|
| **TCP** | SYN floods, ACK floods, malformed TCP | ~20 |
| **UDP** | Generic UDP floods, amplification attacks | ~49 |
| **Advanced** | Enterprise Adaptive DDoS Protection | ~11 |
| **ESP** | IPSec traffic detection | ~8 |
| **GRE** | GRE tunnel attack patterns | ~7 |
| **DNS** | DNS amplification, malformed queries | ~5 |
| **ICMP** | ICMP/ICMPv6 floods | ~4 |
| **SIP** | VoIP SIP attack patterns | ~4 |

### Rule Actions

| Action | Description | Icon |
|--------|-------------|------|
| `block` | Block traffic immediately | 🛑 |
| `log` | Log only (monitor mode) | 📝 |
| `ddos_dynamic` | Dynamic sensitivity (auto-adjust) | 🔄 |

### Customizable vs Read-Only Rules

- **Customizable (29 rules)**: Can change action between allowed options
- **Read-Only (95 rules)**: Fixed by Cloudflare, cannot be modified

### Menu Options

| Option | Function | Description |
|--------|----------|-------------|
| `[s]` | DDoS Status | Overview of all L3/4 DDoS rules and actions |
| `[l]` | List Rules | Show all 29 customizable rules by category |
| `[m]` | Modify | Change action for a specific rule |
| `[o]` | Overrides | View account-specific rule overrides |

### Example: View DDoS Status

```
Select option: s

============================================================
 DDOS PROTECTION STATUS
============================================================

Fetching DDoS managed ruleset...

🛡️  L3/4 DDoS Managed Ruleset
   Version: 3032
   Last Updated: 2026-01-20T11:55:08

📊 Total Rules: 124
   ├─ Customizable: 29
   └─ Read-only: 95

📈 Current Actions:
   🛑 block            61 rules - Block traffic immediately
   🔄 ddos_dynamic     46 rules - Dynamic sensitivity (auto-adjust)
   📝 log              17 rules - Log only (monitor mode)

🏷️  Customizable Categories:
   - advanced        11 rules
   - generic          6 rules
   - esp              4 rules
   - gre              4 rules
   - sip              2 rules
   - udp              2 rules
```

### Example: Modify Rule Action

```
Select option: m

============================================================
 EDIT DDOS RULE SENSITIVITY
============================================================

Select category:
  [1] ADVANCED (11 rules)
  [2] ESP (4 rules)
  [3] GENERIC (6 rules)
  ...

Select category [1-6]: 3

GENERIC Rules:
  [1] TCP-0001      🛑 block        Generic high-volume TCP SYN traffic
  [2] UDP-0004      📝 log          UDP traffic flood in non-ephemeral
  [3] UDP-0001      🔄 ddos_dynamic Generic high-volume UDP traffic flows

Select rule [1-6]: 2

============================================================
Rule: UDP-0004
Description: UDP traffic flood in non-ephemeral port range
Current Action: log
Allowed Actions: block, ddos_dynamic, log
============================================================

Select new action:
  [1] 🛑 block           - Block traffic immediately
  [2] 🔄 ddos_dynamic    - Dynamic sensitivity (auto-adjust)
  [3] 📝 log             - Log only (monitor mode)

Select action [1-3]: 1

Confirm? [Y/n]: Y

Applying override...
✅ Override applied! Rule UDP-0004 now set to 'block'
```

### API Endpoint for Overrides

Overrides are stored in the account's root ruleset for the `ddos_l4` phase:

```bash
# View current overrides
curl -s "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/rulesets/${ROOT_RULESET_ID}" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" | jq

# Get L3/4 DDoS managed ruleset rules
curl -s "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/rulesets/3b64149bfa6e4220bbbc2bd6db589552" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" | jq '.result.rules | length'
```

---

## Best Practices

### Threshold Selection

| Traffic Type | Recommended BPS | Recommended PPS |
|--------------|-----------------|-----------------|
| Low traffic servers | 1-2 Gbps | 200-300k pps |
| Medium traffic | 2-4 Gbps | 300-500k pps |
| High traffic | 5-10 Gbps | 500k-1M pps |

**Tips**:
- Start with higher thresholds and lower gradually
- Monitor normal traffic patterns for 1-2 weeks first
- Avoid ZScore rules if you have irregular traffic patterns (backups, etc.)

### Rule Naming Convention

```
DDoS Protection {TYPE} {PREFIX_WITH_DASH}
```

Examples:
- `DDoS Protection BPS 185.54.81.0-24`
- `DDoS Protection PPS 185.54.82.0-24`

### Backup Before Changes

Always export configuration before making bulk changes:
```bash
python3 cloudflare-rules-manager.py
# Select [e] Export configuration
```

---

## Troubleshooting

### Rules Not Triggering

1. **Check threshold**: May be set too high for your traffic
2. **Check duration**: Traffic must exceed threshold for full duration
3. **Verify prefix**: Rule must match exact prefix being attacked

### False Positives

1. **Lower sensitivity** for ZScore rules
2. **Increase threshold** for BPS/PPS rules
3. **Increase duration** to filter out traffic spikes

### API Errors

```bash
# Test API connectivity
curl -s "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules" \
  -H "X-Auth-Email: ${AUTH_EMAIL}" \
  -H "X-Auth-Key: ${AUTH_KEY}" | jq
```

Common errors:
- **Authentication failed**: Check API credentials
- **Not found**: Account doesn't have Magic Transit
- **Rate limited**: Too many API requests

---

## Changelog

### v1.4 (2026-01-20)
- **DDoS Sensitivity Management** - Full control of L3/4 DDoS Managed Ruleset
  - New menu section: DDOS SENSITIVITY
  - `[s]` DDoS protection status - Overview of all 124 rules
  - `[l]` List customizable DDoS rules - 29 rules grouped by category
  - `[m]` Modify rule sensitivity/action - Change block/log/dynamic
  - `[o]` View current overrides - Account-specific customizations
  - Categories: TCP, UDP, Advanced, ESP, GRE, DNS, ICMP, SIP
  - Actions: block (🛑), log (📝), ddos_dynamic (🔄)
- Added comprehensive documentation section for DDoS sensitivity

### v1.3 (2026-01-20)
- **Advanced DDoS (sFlow) Support** - Full management of fingerprint-based rules
  - New menu option `[4]` to list advanced DDoS rules
  - New menu option `[9]` to add advanced DDoS rules
  - Delete by type now includes Advanced DDoS option
  - Status display shows advanced DDoS rule count
  - Bulk creation for all IPv4 or all prefixes including IPv6
- Updated menu layout with new numbering
- Added Advanced DDoS rule type documentation:
  - API payload format with `type: "advanced_ddos"`
  - `prefix_match` modes (`subnet` vs `exact`)
  - How fingerprint-based detection works
  - When to use advanced DDoS rules
- Added API reference for creating advanced DDoS rules

### v1.2 (2026-01-20)
- Added IPv6 prefix `2a02:4460:1::/48` to GOLINE_PREFIXES
- Updated active rules count to 10 (BPS/PPS for all 5 prefixes)

### v1.1 (2026-01-19)
- Added detailed documentation on Global API Key authentication
- Added Rule Generation Details section:
  - Static rules (BPS/PPS) API payload format
  - Dynamic rules (ZScore) API payload format
  - sFlow-based anomaly detection explanation
  - Threshold conversion formulas
- Documented why GOLINE removed ZScore rules

### v1.0 (2026-01-19)
- Initial documentation
- Interactive menu reference
- Rule types (BPS, PPS, ZScore)
- API reference with curl examples

---

## Related Documentation

- [PREFIX_MANAGER.md](PREFIX_MANAGER.md) - Manual prefix management
- [AUTOWITHDRAW.md](AUTOWITHDRAW.md) - Automatic withdrawal after attacks
- [WEBHOOK_RECEIVER.md](WEBHOOK_RECEIVER.md) - Receiving MNM notifications

---

*GOLINE SOC - Cloudflare Magic Transit Integration*
