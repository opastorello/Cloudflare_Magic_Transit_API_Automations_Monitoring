#!/bin/bash

# Cloudflare sFlow DDoS Rules - GOLINE SA
ACCOUNT_ID="YOUR_CLOUDFLARE_ACCOUNT_ID"
AUTH_EMAIL="YOUR_CLOUDFLARE_EMAIL"
AUTH_KEY="YOUR_CLOUDFLARE_GLOBAL_API_KEY"
API_BASE="https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/mnm/rules"

echo "========================================"
echo " Cloudflare sFlow DDoS Rules Setup"
echo " GOLINE SA"
echo "========================================"
echo ""

# Prima elimina la regola di test
echo "Deleting test rule..."
curl -s -X DELETE "${API_BASE}/91306c92d9334d5f98f604c0248187cd" \
  --header "X-Auth-Email: ${AUTH_EMAIL}" \
  --header "X-Auth-Key: ${AUTH_KEY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ Deleted' if d.get('success') else '✗ Failed')"
echo ""

# Crea le regole sFlow DDoS
echo "Creating sFlow DDoS rules..."
echo ""

for prefix in "185.54.80.0/24" "185.54.81.0/24" "185.54.82.0/24" "185.54.83.0/24" "2a02:4460:1::/48"; do
    echo "Creating sFlow DDoS rule for ${prefix}..."
    curl -s -X POST "${API_BASE}" \
      --header "X-Auth-Email: ${AUTH_EMAIL}" \
      --header "X-Auth-Key: ${AUTH_KEY}" \
      --header "Content-Type: application/json" \
      --data "{
        \"name\": \"sFlow DDoS Detection ${prefix}\",
        \"prefixes\": [\"${prefix}\"],
        \"automatic_advertisement\": true,
        \"type\": \"sflow\"
      }" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get('success'):
    print(f'✓ Created: {d[\"result\"][\"name\"]} (ID: {d[\"result\"][\"id\"][:8]}...)')
else:
    print(f'✗ Failed: {d.get(\"errors\", [{}])[0].get(\"message\", \"Unknown error\")}')"
    echo ""
done

echo "========================================"
echo "Final rules list:"
echo ""
curl -s -X GET "${API_BASE}" \
  --header "X-Auth-Email: ${AUTH_EMAIL}" \
  --header "X-Auth-Key: ${AUTH_KEY}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d.get('result',[]):
    t = r.get('type','threshold')
    auto = '✓' if r.get('automatic_advertisement') else '✗'
    name = r.get('name','N/A')
    if 'bandwidth_threshold' in r:
        th = f\"{r['bandwidth_threshold']/1000000000:.0f} Gbps\"
    elif 'packet_threshold' in r:
        th = f\"{r['packet_threshold']/1000:.0f}k pps\"
    else:
        th = 'ML detection'
    print(f'[{auto}] {name}')
    print(f'    Type: {t} | Threshold: {th}')
"

echo ""
echo "========================================"
echo "Done!"
echo ""
echo "⚠️  IMPORTANT: Rotate your API credentials!"
echo "========================================"
