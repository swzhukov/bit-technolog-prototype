#!/usr/bin/env python3
"""RBAC matrix test via paramiko."""
import paramiko
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

# Connect
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)

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

# Run
cmd = f'python3 -c {repr(test_py)}'
stdin, stdout, stderr = client.exec_command(cmd, timeout=240)
out = stdout.read().decode()
err = stderr.read().decode()
client.close()

# Parse
print('STDOUT len:', len(out))
print('STDOUT:', out[:500])
if err:
    print('STDERR:', err[:500])
try:
    data = json.loads(out)
    with open('/workspace/audit/rbac_matrix.json', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n===SAVED {len(USERS) * len(ENDPOINTS_GET)} tests===")
    for user, paths in data.items():
        for path, code in paths.items():
            if code not in (200, 303, 404):
                print(f"  ⚠ {user} {path}: {code}")
except Exception as e:
    print(f"Parse error: {e}")
