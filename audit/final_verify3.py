"""Финальная верификация - все тесты в одной SSH команде."""
import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)

# Build a single bash script
TESTS = [
    ('update_valid', '/api/operations/32/update', 'json', '{"field":"name","value":"test"}', [200, 200, 200, 403]),
    ('update_empty', '/api/operations/32/update', 'json', '{}', [400, 400, 400, 400]),
    ('update_form', '/api/operations/32/update', 'form', 'input=', [400, 400, 400, 400]),
    ('update_99999', '/api/operations/99999/update', 'json', '{"field":"name","value":"x"}', [404, 404, 404, 404]),
    ('confirm_valid', '/api/operations/32/confirm', 'json', '{"new_time": 5.0}', [200, 200, 200, 403]),
    ('regenerate', '/api/tech-cards/1/regenerate', 'json', '{}', [200, 200, 200, 403]),
    ('approve', '/api/tech-cards/1/approve', 'json', '{}', [200, 200, 403, 403]),
    ('process_notice', '/api/change-notices/1/process', 'json', '{"decision":"manual_review"}', [200, 200, 200, 403]),
    ('resolve_valid', '/notices/1/resolve', 'form', 'decision=manual_review', [303, 303, 303, 403]),
    ('resolve_999', '/notices/999/resolve', 'form', 'decision=manual_review', [404, 404, 404, 403]),
]

USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

# Build script
lines = []
for user in USERS:
    lines.append(f"echo '\\n--- {user} ---'")
    lines.append(f"rm -f /tmp/c.jar")
    lines.append(f"curl -sk -c /tmp/c.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null")
    for name, path, ctype, body, exp in TESTS:
        if ctype == 'json':
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{body}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        else:
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -d '{body}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        lines.append(f"echo -n '{name}: ' && {cmd} && echo ''")

cmd_str = ' && '.join(lines)
stdin, stdout, stderr = client.exec_command(cmd_str, timeout=120)
out = stdout.read().decode()
err = stderr.read().decode()
client.close()

# Parse
print('===RAW===')
print(out[:2000])
print('---')

n_pass = 0
n_total = 0
for line in out.split('\n'):
    if ':' in line and '---' not in line:
        parts = line.split(':')
        if len(parts) >= 2:
            name = parts[0].strip()
            try:
                code = int(parts[-1].strip())
            except:
                continue
            # Find expected
            for tn, _, _, _, exp in TESTS:
                if tn == name:
                    # Find user from line above
                    pass  # skip detailed analysis
            # Simple: count
            n_total += 1
            if code in (200, 201, 303, 400, 403, 404):
                n_pass += 1

# Better: parse with user context
current_user = None
for line in out.split('\n'):
    if line.startswith('--- '):
        current_user = line.replace('--- ', '').replace(' ---', '').strip()
    elif ':' in line and not line.startswith('---'):
        name = line.split(':')[0].strip()
        try:
            code = int(line.rsplit(':', 1)[-1].strip())
        except:
            continue
        if current_user and name:
            for tn, _, _, _, exp in TESTS:
                if tn == name:
                    idx = USERS.index(current_user)
                    expected = exp[idx]
                    marker = '✅' if code == expected else f'❌ (exp {expected})'
                    print(f"  {name:25}  {current_user:12}  {code:4}  {marker}")

print(f"\n=== TOTAL TESTS ===")
