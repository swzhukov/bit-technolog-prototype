#!/usr/bin/env python3
"""RBAC matrix test on prod."""
import subprocess
import os
import json

BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']
ENDPOINTS_GET = [
    ('/', '200'),
    ('/products', '200'),
    ('/notices', '200'),
    ('/metrics', '200'),
    ('/profiles', '200'),
    ('/llm-admin', '200'),
    ('/settings', '200'),
    ('/knowledge', '200'),
    ('/help', '200'),
    ('/rs', '200'),
    ('/details/new', '200'),
    ('/health', '200'),
    ('/detail/3', '200'),
    ('/detail/999', '404'),
    ('/notices/1', '200'),
    ('/notices/999', '404'),
    ('/items/3/generate', '200'),
    ('/notices/new', '200'),
    ('/api/items', '200'),
    ('/api/rs/list', '200'),
    ('/api/change-notices', '200'),
    ('/api/change-notices/1', '200'),
    ('/api/tech-cards/1/rs-preview', '200'),
    ('/api/tech-cards/1/evidence', '200'),
    ('/api/rs/download/nonexistent.xml', '404'),
    ('/api/rs/download/..%2Fapp.py', '404'),
]

# Run via ssh
test_py = f"""
import json, subprocess
USERS = {json.dumps(USERS)}
ENDPOINTS = {json.dumps(ENDPOINTS_GET)}
results = {{}}
for user in USERS:
    subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
    subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', f'username={{user}}&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)
    results[user] = {{}}
    for path, _ in ENDPOINTS:
        r = subprocess.run(['curl', '-sk', '-b', '/tmp/c.jar', '-o', '/dev/null', '-w', '%{{http_code}}', f'https://localhost:8081{{path}}'], capture_output=True, text=True, timeout=30)
        try:
            results[user][path] = int(r.stdout.strip())
        except:
            results[user][path] = -1
print(json.dumps(results, ensure_ascii=False))
"""

# Write test to server and run
ssh_cmd = ['sshpass', '-p', BEGET, 'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
           'root@seefeesnahurid.beget.app',
           f'python3 -c {repr(test_py)}']

r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=300)
print('STDOUT:', r.stdout[:3000])
print('STDERR:', r.stderr[:500])

# Parse JSON output
try:
    json_start = r.stdout.find('{')
    json_end = r.stdout.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        data = json.loads(r.stdout[json_start:json_end])
        with open('/workspace/audit/rbac_matrix.json', 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(USERS) * len(ENDPOINTS_GET)} tests to /workspace/audit/rbac_matrix.json")
except Exception as e:
    print(f"Parse error: {e}")
