#!/bin/bash

# Cloudflare sFlow DDoS Rules - GOLINE SA
ACCOUNT_ID="YOUR_CLOUDFLARE_ACCOUNT_ID"
API_TOKEN="YOUR_API_TOKEN"
API_BASE="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules"

echo "Creating sFlow DDoS rules..."
echo ""

# 185.54.80.0/24
echo "Creating rule for 185.54.80.0/24..."
curl -s -X POST "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "sFlow DDoS Detection 185.54.80.0/24",
    "prefixes": ["185.54.80.0/24"],
    "automatic_advertisement": true,
    "type": "sflow"
  }' | python3 -m json.tool
echo ""

# 185.54.81.0/24
echo "Creating rule for 185.54.81.0/24..."
curl -s -X POST "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "sFlow DDoS Detection 185.54.81.0/24",
    "prefixes": ["185.54.81.0/24"],
    "automatic_advertisement": true,
    "type": "sflow"
  }' | python3 -m json.tool
echo ""

# 185.54.82.0/24
echo "Creating rule for 185.54.82.0/24..."
curl -s -X POST "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "sFlow DDoS Detection 185.54.82.0/24",
    "prefixes": ["185.54.82.0/24"],
    "automatic_advertisement": true,
    "type": "sflow"
  }' | python3 -m json.tool
echo ""

# 185.54.83.0/24
echo "Creating rule for 185.54.83.0/24..."
curl -s -X POST "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "sFlow DDoS Detection 185.54.83.0/24",
    "prefixes": ["185.54.83.0/24"],
    "automatic_advertisement": true,
    "type": "sflow"
  }' | python3 -m json.tool
echo ""

# 2a02:4460:1::/48 (IPv6)
echo "Creating rule for 2a02:4460:1::/48 (IPv6)..."
curl -s -X POST "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{
    "name": "sFlow DDoS Detection 2a02:4460:1::/48",
    "prefixes": ["2a02:4460:1::/48"],
    "automatic_advertisement": true,
    "type": "sflow"
  }' | python3 -m json.tool
echo ""

echo "========================================"
echo "Listing all rules..."
curl -s -X GET "${API_BASE}" \
  -H "Authorization: Bearer ${API_TOKEN}" | python3 -m json.tool

echo ""
echo "Done! Remember to rotate your API token."
