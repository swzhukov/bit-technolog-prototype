"""Финальная верификация на prod - без дубликатов."""
import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()

# Уникальные тесты
TESTS = [
    # (path, ctype, body, expected_per_user)
    # admin/tech/main_tech получают разный ответ
    ('update_valid', '/api/operations/32/update', 'json', {"field":"name","value":"test"}, [200, 200, 200, 403]),
    ('update_empty_json', '/api/operations/32/update', 'json', {}, [400, 400, 400, 400]),
    ('update_form', '/api/operations/32/update', 'form', 'input=', [400, 400, 400, 400]),
    ('update_99999', '/api/operations/99999/update', 'json', {"field":"name","value":"x"}, [404, 404, 404, 404]),
    ('confirm_valid', '/api/operations/32/confirm', 'json', {"new_time": 5.0}, [200, 200, 200, 403]),
    ('regenerate', '/api/tech-cards/1/regenerate', 'json', {}, [200, 200, 200, 403]),
    ('approve', '/api/tech-cards/1/approve', 'json', {}, [200, 200, 403, 403]),
    ('process_notice', '/api/change-notices/1/process', 'json', {"decision":"manual_review"}, [200, 200, 200, 403]),
    ('resolve_valid', '/notices/1/resolve', 'form', 'decision=manual_review', [303, 303, 303, 403]),
    ('resolve_999', '/notices/999/resolve', 'form', 'decision=manual_review', [404, 404, 404, 403]),
]

test_py = f"""
import json, subprocess
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']
TESTS = {json.dumps(TESTS)}
results = {{}}
for user in USERS:
    subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
    subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', f'username={{user}}&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)
    results[user] = {{}}
    for name, path, ctype, body, exp in TESTS:
        cmd = ['curl', '-sk', '-b', '/tmp/c.jar', '-X', 'POST', '-o', '/dev/null', '-w', '%{{http_code}}']
        if ctype == 'json':
            cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '-H', 'Content-Type: application/json', '-d', json.dumps(body)]
        else:
            cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '-d', body]
        cmd.append(f'https://localhost:8081{{path}}')
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        try:
            results[user][name] = int(r.stdout.strip())
        except:
            results[user][name] = -1
with open('/tmp/final.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False)
print('OK')
"""
with sftp.file('/tmp/final.py', 'w') as f:
    f.write(test_py)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/final.py', timeout=120)
print('out:', stdout.read().decode()[:200])
client.close()

import time
time.sleep(1)
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client2.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp2 = client2.open_sftp()
with sftp2.file('/tmp/final.json', 'r') as f:
    data = json.load(f)
sftp2.close()
client2.close()

n_pass = 0
n_total = 0
print(f"\n{'Test':30}  {'techadmin':>10}  {'vorobyev':>10}  {'tarrietsky':>10}  {'golubev':>10}")
print("-" * 80)
for name, path, ctype, body, exp in TESTS:
    row = f"{name:30}"
    for i, user in enumerate(['techadmin', 'vorobyev', 'tarrietsky', 'golubev']):
        code = data[user][name]
        expected = exp[i]
        marker = '✅' if code == expected else '❌'
        n_total += 1
        if code == expected: n_pass += 1
        row += f"  {code}({marker})"
    print(row)

print(f"\n=== TOTAL: {n_pass}/{n_total} passed ===")
