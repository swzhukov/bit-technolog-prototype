#!/usr/bin/env python3
"""RBAC matrix test via paramiko (write script to file)."""
import paramiko
import os
import json

BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']
ENDPOINTS_GET = [
    ('/', '200'), ('/products', '200'), ('/notices', '200'),
    ('/metrics', '200'), ('/profiles', '200'), ('/llm-admin', '200'),
    ('/settings', '200'), ('/knowledge', '200'), ('/help', '200'),
    ('/rs', '200'), ('/details/new', '200'), ('/health', '200'),
    ('/detail/3', '200'), ('/detail/999', '404'), ('/notices/1', '200'),
    ('/notices/999', '404'), ('/items/3/generate', '200'), ('/notices/new', '200'),
    ('/api/items', '200'), ('/api/rs/list', '200'),
    ('/api/change-notices', '200'), ('/api/change-notices/1', '200'),
    ('/api/tech-cards/1/rs-preview', '200'), ('/api/tech-cards/1/evidence', '200'),
    ('/api/rs/download/nonexistent.xml', '404'),
    ('/api/rs/download/..%2Fapp.py', '404'),
]

# Write test to a file via SFTP, then run
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()

# Write test
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
with open('/tmp/rbac_out.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False)
print('OK')
"""

with sftp.file('/tmp/rbac_test.py', 'w') as f:
    f.write(test_py)
sftp.close()

# Run
stdin, stdout, stderr = client.exec_command('python3 /tmp/rbac_test.py', timeout=240)
out = stdout.read().decode()
err = stderr.read().decode()
print('out:', out[:200])
print('err:', err[:500])
client.close()

# Read result
import time
time.sleep(2)
# Get result via SSH
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client2.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp2 = client2.open_sftp()
with sftp2.file('/tmp/rbac_out.json', 'r') as f:
    data = json.load(f)
sftp2.close()
client2.close()

with open('/workspace/audit/rbac_matrix.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n===SAVED {len(USERS) * len(ENDPOINTS_GET)} tests===")
# Print anomalies
for user, paths in data.items():
    for path, code in paths.items():
        # Expected rules:
        # /metrics, /profiles — admin, main_tech
        # /llm-admin, /settings — admin only
        # /health, /api/* — all
        # /items/3/generate, /notices/new — admin, main_tech, technologist
        # /api/rs/download — all
        pass

# Show matrix
print()
for path, _ in ENDPOINTS_GET:
    row = f"{path:45}"
    for user in USERS:
        code = data[user][path]
        row += f"  {code:>3}"
    print(row)
print(f"{'USER':<45}  " + '  '.join(USERS))
