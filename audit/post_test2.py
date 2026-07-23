#!/usr/bin/env python3
"""POST endpoint RBAC + CSRF + JSON validation (без LLM)."""
import paramiko
import os
import json

BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

# Без тяжёлых (без /items/{id}/generate - 24 сек LLM)
POST_TESTS = [
    # CSRF bypass (no XRW, no Origin) - должен быть 403
    ('/api/operations/32/update', 'input=', {}, '403'),
    # Valid JSON with CSRF
    ('/api/operations/32/update', '{"field":"name","value":"test"}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '200'),
    # Invalid JSON (form-encoded to json endpoint)
    ('/api/operations/32/update', 'input=', {'X-Requested-With': 'XMLHttpRequest'}, '400'),
    # missing field
    ('/api/operations/32/update', '{}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '400'),
    # missing operation
    ('/api/operations/99999/update', '{"field":"name","value":"x"}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '404'),
    # metrics/record-green (admin only)
    ('/metrics/record-green', '', {'X-Requested-With': 'XMLHttpRequest'}, 'admin=303, others=403'),
    # change-notices/1/process
    ('/api/change-notices/1/process', '{"decision":"manual_review"}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '200'),
    # regenerate
    ('/api/tech-cards/1/regenerate', '{}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '200'),
    # approve
    ('/api/tech-cards/1/approve', '{}', {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, '200'),
    # generate-diff (lazy, no LLM call)
    ('/notices/1/generate-diff', '', {'X-Requested-With': 'XMLHttpRequest'}, '200'),
    # login (no CSRF needed)
    ('/login', 'username=techadmin&password=demo', {}, '303'),
    # logout
    ('/logout', '', {}, '303'),
    # settings/llm (admin only)
    ('/settings/llm', 'provider_id=1', {'X-Requested-With': 'XMLHttpRequest'}, 'admin=303, others=403'),
    # notices/1/resolve
    ('/notices/1/resolve', 'decision=manual_review&notes=test', {'X-Requested-With': 'XMLHttpRequest'}, '303'),
    # 404 invalid id
    ('/notices/999/resolve', 'decision=manual_review', {'X-Requested-With': 'XMLHttpRequest'}, '404'),
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()

test_py = f"""
import json, subprocess
USERS = {json.dumps(USERS)}
POST_TESTS = {json.dumps(POST_TESTS)}
results = {{}}
for user in USERS:
    subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
    subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', f'username={{user}}&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)
    results[user] = {{}}
    for path, data, hdrs, _ in POST_TESTS:
        cmd = ['curl', '-sk', '-b', '/tmp/c.jar', '-X', 'POST', '-o', '/dev/null', '-w', '%{{http_code}}']
        if data:
            cmd += ['-d', data]
        for k, v in hdrs.items():
            cmd += ['-H', f'{{k}}: {{v}}'.format(k=k, v=v)]
        cmd.append(f'https://localhost:8081{{path}}'.format(path=path))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        try:
            results[user][path] = int(r.stdout.strip())
        except:
            results[user][path] = -1
with open('/tmp/post_out.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False)
print('OK')
"""
with sftp.file('/tmp/post_test.py', 'w') as f:
    f.write(test_py)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/post_test.py', timeout=180)
out = stdout.read().decode()
err = stderr.read().decode()
print('out:', out[:200])
if err and 'Traceback' in err:
    print('err:', err[:2000])
client.close()

import time
time.sleep(2)
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client2.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp2 = client2.open_sftp()
try:
    with sftp2.file('/tmp/post_out.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print('NO OUTPUT FILE')
    data = {}
sftp2.close()
client2.close()

with open('/workspace/audit/post_matrix.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n===POST MATRIX ({len(USERS) * len(POST_TESTS)} tests)===")
for path, _, _, _ in POST_TESTS:
    row = f"{path:50}"
    for user in USERS:
        code = data.get(user, {}).get(path, '?')
        row += f"  {code:>3}"
    print(row)
