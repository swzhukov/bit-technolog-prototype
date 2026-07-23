"""V2 верификация на prod - новые находки."""
import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']

# V2 tests
TESTS = [
    # F2-001: header должен показать username (не ФИО)
    ('/products', '200', 'all'),
    # F2-003: api_notice НЕ должен звать LLM (нет ai_diff в response)
    ('/api/change-notices/1', '200', 'all'),
    ('/api/change-notices/999', '404', 'all'),
    # F2-003: новый endpoint /api/change-notices/{id}/diff
    ('/api/change-notices/1/diff', '200', 'admin+main_tech+tech'),
    ('/api/change-notices/999/diff', '404', 'all'),
    # F2-004: /notices/999/generate-diff → 404
    ('/notices/999/generate-diff', '404', 'all'),
    # F2-005: /api/operations/99999/confirm → 404
    ('/api/operations/99999/confirm', '404', 'all'),
    # V1 тесты должны быть тоже OK
    ('/api/operations/32/confirm', '200', 'admin+main_tech+tech'),
    ('/api/operations/32/confirm', '403', 'workshop_chief'),
    ('/api/tech-cards/1/regenerate', '200', 'admin+main_tech+tech'),
    ('/api/tech-cards/1/approve', '200', 'admin+main_tech'),
    ('/api/tech-cards/1/approve', '403', 'tech+chief'),
]

# Build script
lines = []
for user in USERS:
    lines.append(f"echo '\\n--- {user} ---'")
    lines.append(f"rm -f /tmp/c.jar")
    lines.append(f"curl -sk -c /tmp/c.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null")
    for name, path, expected in TESTS:
        if '/api/change-notices/1/diff' in name or '/api/change-notices/999/diff' in name or '/notices/999/generate-diff' in name or '/api/operations/99999/confirm' in name:
            # POST
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        elif '/api/' in name and 'confirm' in name:
            # POST JSON
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{{}}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        elif '/api/' in name and ('regenerate' in name or 'approve' in name):
            # POST JSON
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{{}}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        else:
            # GET
            cmd = f"curl -sk -b /tmp/c.jar -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        lines.append(f"echo -n '{name} ({expected}): ' && {cmd} && echo ''")

# Header check
lines.append("echo '\\n--- HEADER 152-ФЗ ---'")
lines.append("curl -sk -b /tmp/c.jar https://localhost:8081/products | grep -E 'display_name|username' | head -3")

cmd_str = ' && '.join(lines)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command(cmd_str, timeout=120)
out = stdout.read().decode()
client.close()

print('===V2 TEST OUTPUT===')
print(out[:3000])
