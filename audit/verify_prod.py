import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

# All endpoints to test (full matrix)
ENDPOINTS_GET = [
    ('/', 200), ('/products', 200), ('/notices', 200),
    ('/metrics', [200, 200, 403, 403]),
    ('/profiles', [200, 200, 403, 403]),
    ('/llm-admin', [200, 403, 403, 403]),
    ('/settings', [200, 403, 403, 403]),
    ('/knowledge', 200), ('/help', 200),
    ('/rs', 200), ('/details/new', 200), ('/health', 200),
    ('/detail/3', 200), ('/detail/999', 404),
    ('/notices/1', 200), ('/notices/999', 404),
    ('/notices/new', 200), ('/items/3/generate', 200),
    ('/api/items', 200), ('/api/rs/list', 200),
    ('/api/change-notices', 200),
    ('/api/change-notices/1', 200),
    ('/api/tech-cards/1/rs-preview', 200),
    ('/api/tech-cards/1/evidence', 200),
    ('/api/rs/download/nonexistent.xml', 404),
]

POST_TESTS = [
    # F-001: admin update → 200
    ('/api/operations/32/update', 'json', {"field":"name","value":"test"}, [200, 200, 200, 403]),
    # F-001: workshop_chief update → 403
    ('/api/operations/32/update', 'json', {"field":"name","value":"test"}, [200, 200, 200, 403]),
    # F-002: admin confirm → 200
    ('/api/operations/32/confirm', 'json', {"new_time": 5.0}, [200, 200, 200, 403]),
    # F-004: admin regenerate → 200
    ('/api/tech-cards/1/regenerate', 'json', {}, [200, 200, 200, 403]),
    # F-005: admin approve → 200
    ('/api/tech-cards/1/approve', 'json', {}, [200, 200, 403, 403]),
    # F-005: technologist approve → 403
    ('/api/tech-cards/1/approve', 'json', {}, [200, 200, 403, 403]),
    # F-006: workshop_chief process notice → 403
    ('/api/change-notices/1/process', 'json', {"decision":"manual_review"}, [200, 200, 200, 403]),
    # F-007: workshop_chief resolve → 403
    ('/notices/1/resolve', 'form', 'decision=manual_review', [303, 303, 303, 403]),
    # F-008: 999 → 404
    ('/notices/999/resolve', 'form', 'decision=manual_review', [404, 404, 404, 404]),
    # CSRF bypass → 403
    ('/api/operations/32/update', 'form', 'input=', [403, 403, 403, 403]),
    # invalid JSON → 400
    ('/api/operations/32/update', 'json', {}, [400, 400, 400, 400]),
    # missing field → 400
    ('/api/operations/32/update', 'json', {}, [400, 400, 400, 400]),
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()

test_py = f"""
import json, subprocess
USERS = {json.dumps(USERS)}
ENDPOINTS_GET = {json.dumps(ENDPOINTS_GET)}
POST_TESTS = {json.dumps(POST_TESTS)}

results = {{'GET': {{}}, 'POST': {{}}}}

for user in USERS:
    subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
    subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', f'username={{user}}&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)
    
    # GET
    results['GET'][user] = {{}}
    for path, exp in ENDPOINTS_GET:
        r = subprocess.run(['curl', '-sk', '-b', '/tmp/c.jar', '-o', '/dev/null', '-w', '%{{http_code}}', f'https://localhost:8081{{path}}'], capture_output=True, text=True, timeout=15)
        try:
            results['GET'][user][path] = int(r.stdout.strip())
        except:
            results['GET'][user][path] = -1
    
    # POST
    results['POST'][user] = {{}}
    for path, ctype, body, exp_list in POST_TESTS:
        cmd = ['curl', '-sk', '-b', '/tmp/c.jar', '-X', 'POST', '-o', '/dev/null', '-w', '%{{http_code}}']
        if ctype == 'json':
            cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '-H', 'Content-Type: application/json', '-d', json.dumps(body)]
        else:
            cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '-d', body]
        cmd.append(f'https://localhost:8081{{path}}'.format(path=path))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        try:
            results['POST'][user][path] = int(r.stdout.strip())
        except:
            results['POST'][user][path] = -1

with open('/tmp/verify.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False)
print('OK')
"""
with sftp.file('/tmp/verify.py', 'w') as f:
    f.write(test_py)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/verify.py', timeout=300)
print('out:', stdout.read().decode()[:200])
if stderr.read():
    print('err:', stderr.read().decode()[:500])
client.close()

import time
time.sleep(2)
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client2.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp2 = client2.open_sftp()
with sftp2.file('/tmp/verify.json', 'r') as f:
    data = json.load(f)
sftp2.close()
client2.close()

# Analyze
print("\n=== GET MATRIX ===")
for path, exp in ENDPOINTS_GET:
    row = f"{path:45}"
    fail = False
    for i, user in enumerate(USERS):
        code = data['GET'][user][path]
        if isinstance(exp, list):
            expected = exp[i]
        else:
            expected = exp
        marker = '✅' if code == expected else '❌'
        if code != expected: fail = True
        row += f"  {code}({marker})"
    if fail: print(row)

print("\n=== POST MATRIX ===")
for path, ctype, body, exp_list in POST_TESTS:
    row = f"{path:50}"
    fail = False
    for i, user in enumerate(USERS):
        code = data['POST'][user][path]
        expected = exp_list[i]
        marker = '✅' if code == expected else '❌'
        if code != expected: fail = True
        row += f"  {code}({marker})"
    if fail: print(row)

# Count total
n_total = 0
n_pass = 0
for path, exp in ENDPOINTS_GET:
    for i, user in enumerate(USERS):
        code = data['GET'][user][path]
        expected = exp[i] if isinstance(exp, list) else exp
        n_total += 1
        if code == expected: n_pass += 1
for path, ctype, body, exp_list in POST_TESTS:
    for i, user in enumerate(USERS):
        code = data['POST'][user][path]
        expected = exp_list[i]
        n_total += 1
        if code == expected: n_pass += 1
print(f"\n=== TOTAL: {n_pass}/{n_total} passed ===")
