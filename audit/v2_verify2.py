import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)

# Test one by one
TESTS = [
    ('/api/change-notices/1', 'GET', None),
    ('/api/change-notices/999', 'GET', None),
    ('/api/change-notices/1/diff', 'POST', 'XRW'),
    ('/api/change-notices/999/diff', 'POST', 'XRW'),
    ('/notices/999/generate-diff', 'POST', 'XRW'),
    ('/api/operations/99999/confirm', 'POST', 'XRW-JSON'),
    ('/api/operations/32/confirm', 'POST', 'XRW-JSON'),
    ('/api/tech-cards/1/regenerate', 'POST', 'XRW-JSON'),
    ('/api/tech-cards/1/approve', 'POST', 'XRW-JSON'),
]

for user in ['techadmin', 'tarrietsky', 'golubev']:
    print(f"\n--- {user} ---")
    # Login
    stdin, stdout, stderr = client.exec_command(f"rm -f /tmp/c.jar; curl -sk -c /tmp/c.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null", timeout=15)
    stdout.read()
    for path, method, hdr in TESTS:
        if method == 'GET':
            cmd = f"curl -sk -b /tmp/c.jar -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        elif hdr == 'XRW':
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        elif hdr == 'XRW-JSON':
            cmd = f"curl -sk -b /tmp/c.jar -X POST -H 'X-Requested-With: XMLHttpRequest' -H 'Content-Type: application/json' -d '{{}}' -o /dev/null -w '%{{http_code}}' https://localhost:8081{path}"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        try:
            code = int(out)
        except:
            code = -1
        print(f"  {method:4} {path:50} {code}")

# Header check
print("\n--- HEADER 152-ФЗ (для techadmin) ---")
stdin, stdout, stderr = client.exec_command("rm -f /tmp/c.jar; curl -sk -c /tmp/c.jar -X POST -d 'username=techadmin&password=demo' https://localhost:8081/login -o /dev/null; curl -sk -b /tmp/c.jar https://localhost:8081/products | grep -E 'user|techadmin|Тарлецкий' | head -3", timeout=30)
print(stdout.read().decode()[:1000])
client.close()
