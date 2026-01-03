# Quickstart Guide: Integrity Evidence Samples

## Quick Analysis

Run the analysis script to see attack patterns:

```bash
python3 analyze_attack.py
```

This will show:
- Executive summary of the attack
- Timeline analysis (minute-by-minute)
- Attacker identification and classification
- Guardrail effectiveness metrics
- Endpoint targeting analysis
- Attack pattern detection

## Sample Evidence Files

75 JSON files organized by attack phase:

- `01_normal_*.json` (15 files) - Legitimate traffic
- `02_attack_begin_*.json` (5 files) - Attack ramp-up
- `03_rate_limit_denied_*.json` (20 files) - Rate limit blocks
- `04_burst_attack_*.json` (10 files) - Burst attack blocks
- `05_distributed_attack_*.json` (15 files) - Distributed attack
- `06_post_attack_normal_*.json` (10 files) - Return to normal

## Quick Inspection

**View a normal request:**
```bash
cat 01_normal_001_*.json | jq .
```

**View a blocked attack:**
```bash
cat 03_rate_limit_denied_001_*.json | jq .
```

**View a burst attack:**
```bash
cat 04_burst_attack_001_*.json | jq .
```

## Common Queries

**Count allowed vs denied:**
```bash
jq -r '.decision.decision' *.json | sort | uniq -c
```

**Find all attacking IPs:**
```bash
jq -r 'select(.decision.decision == "denied") | .decision.metadata.client_ip' *.json | sort -u
```

**Get attack timeline:**
```bash
jq -r '"\(.decision.timestamp) \(.decision.decision) \(.decision.metadata.client_ip)"' *.json | sort
```

**Extract rate limit metadata:**
```bash
jq -r 'select(.decision.reason == "rate_limit_exceeded") | "\(.decision.metadata.client_ip): \(.decision.metadata.requests_in_window) requests"' *.json
```

**Verify content hashes:**
```bash
for file in 01_normal_001_*.json; do
  echo "Checking $file..."
  jq -c '.decision' "$file" | shasum -a 256
  jq -r '.content_hash' "$file"
done
```

## Key Evidence Fields

Each evidence bundle contains:

```json
{
  "evidence_id": "unique-uuid",
  "timestamp": "when-evidence-created",
  "decision": {
    "decision_id": "unique-decision-id",
    "timestamp": "when-decision-made",
    "trace_id": "opentelemetry-trace-id",
    "span_id": "opentelemetry-span-id",
    "service": "certus-ask",
    "decision": "allowed|denied",
    "reason": "why",
    "guardrail": "which-protection",
    "metadata": {
      "client_ip": "x.x.x.x",
      "endpoint": "/v1/...",
      "requests_in_window": 101,
      "limit": 100
    }
  },
  "content_hash": "sha256-of-decision",
  "signature": "cryptographic-signature",
  "verification_status": "signed"
}
```

## Tutorial Use Cases

### 1. Verify Evidence Integrity

```python
import json
import hashlib

with open('01_normal_001_*.json') as f:
    bundle = json.load(f)

# Recompute content hash
decision_json = json.dumps(bundle['decision'], sort_keys=True, separators=(',', ':'))
computed_hash = hashlib.sha256(decision_json.encode()).hexdigest()

# Compare with stored hash
assert computed_hash == bundle['content_hash']
print("✓ Evidence integrity verified")
```

### 2. Detect Attack Patterns

```python
import json
from collections import defaultdict
from pathlib import Path

# Load all bundles
bundles = []
for file in Path('.').glob('*.json'):
    with open(file) as f:
        bundles.append(json.load(f))

# Group by IP
by_ip = defaultdict(list)
for bundle in bundles:
    ip = bundle['decision']['metadata']['client_ip']
    by_ip[ip].append(bundle['decision'])

# Find attackers (high denial rate)
for ip, decisions in by_ip.items():
    denied = sum(1 for d in decisions if d['decision'] == 'denied')
    if denied > 5:
        print(f"Attacker: {ip} - {denied} requests blocked")
```

### 3. Audit Trail

```python
import json
from datetime import datetime

# Load and sort chronologically
bundles = []
for file in Path('.').glob('*.json'):
    with open(file) as f:
        bundles.append(json.load(f))

bundles.sort(key=lambda b: b['decision']['timestamp'])

# Print audit trail
for bundle in bundles:
    d = bundle['decision']
    timestamp = d['timestamp']
    decision = d['decision']
    ip = d['metadata']['client_ip']
    endpoint = d['metadata']['endpoint']

    print(f"{timestamp} | {decision:8} | {ip:15} | {endpoint}")
```

### 4. Rate Limit Analysis

```python
import json
import statistics

# Analyze request rates
allowed_rates = []
denied_rates = []

for file in Path('.').glob('*.json'):
    with open(file) as f:
        bundle = json.load(f)
        decision = bundle['decision']

        if 'requests_in_window' in decision['metadata']:
            rate = decision['metadata']['requests_in_window']

            if decision['decision'] == 'allowed':
                allowed_rates.append(rate)
            else:
                denied_rates.append(rate)

print(f"Allowed requests/min: {statistics.mean(allowed_rates):.1f} avg")
print(f"Denied requests/min:  {statistics.mean(denied_rates):.1f} avg")
print(f"Rate limit threshold: 100 requests/min")
```

## Regenerate Samples

Modify and re-run the generator:

```bash
python3 generate_samples.py
```

Edit `generate_samples.py` to:
- Change the scenario date/time
- Adjust IP addresses
- Modify rate limits
- Add new attack patterns
- Test different guardrails

## Integration Examples

### With Certus Assurance

```python
# Verify evidence bundle signatures
from certus_assurance import verify_evidence

bundle = load_evidence_bundle('03_rate_limit_denied_001_*.json')
result = verify_evidence(bundle)

if result.verified:
    print("✓ Signature valid")
    print(f"✓ Transparency log entry: {bundle['transparency_log_entry']['uuid']}")
```

### With Analytics

```python
# Send to analytics pipeline
import requests

for file in Path('.').glob('*.json'):
    with open(file) as f:
        bundle = json.load(f)

    # Push to analytics
    requests.post('http://analytics:8080/ingest', json=bundle)
```

### With Monitoring

```python
# Alert on attack patterns
denied_count = sum(1 for b in bundles if b['decision']['decision'] == 'denied')

if denied_count > 10:
    send_alert(f"Attack detected: {denied_count} requests blocked")
```

## Expected Output

When you run `analyze_attack.py`, you should see:

- **Executive Summary**: 40 malicious requests blocked, 0% false positives
- **Timeline**: Normal traffic 14:25-14:31, attack 14:32-14:38, recovery 14:40+
- **Attackers**: 12 attacking IPs identified
- **Guardrails**: Rate limit blocked 100% of attack traffic
- **Endpoints**: `/v1/default/ask` was primary target
- **Patterns**: Sustained attack, burst attack, and distributed attack detected

## Next Steps

1. **Read the full README.md** for detailed schema documentation
2. **Experiment with the analysis script** - modify queries
3. **Create custom scenarios** - edit generate_samples.py
4. **Integrate with your tools** - use evidence in your applications
5. **Test verification** - implement signature checking

## Support

- Schema reference: `certus_integrity/evidence.py`
- Decision logic: `certus_integrity/middleware.py`
- Data models: `certus_integrity/schemas.py`
