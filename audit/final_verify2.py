"""Финальная верификация без SFTP - чтение через stdout."""
import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)

TESTS = [
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

USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

n_pass = 0
n_total = 0
print(f"\n{'Test':30}  {'admin':>10}  {'main_tech':>10}  {'tech':>10}  {'chief':>10}")
print("-" * 80)
for name, path, ctype, body, exp in TESTS:
    row = f"{name:30}"
    for i, user in enumerate(USERS):
        # Login
        stdin, stdout, stderr = client.exec_command(f"rm -f /tmp/c.jar; curl -sk -c /tmp/c.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null", timeout=15)
        stdout.read()
        # Build curl
        if ctype == 'json':
            body_str = json.dumps(body)
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{body_str}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        else:
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -d '{body}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        try:
            code = int(out)
        except:
            code = -1
        expected = exp[i]
        marker = '✅' if code == expected else '❌'
        n_total += 1
        if code == expected: n_pass += 1
        row += f"  {code}({marker})"
    print(row)

print(f"\n=== TOTAL: {n_pass}/{n_total} passed ===")
client.close()
