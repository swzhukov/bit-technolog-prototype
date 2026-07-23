import paramiko
import os
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()
test_py = """
import subprocess
# Login admin
subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', 'username=techadmin&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)
# Confirm cookies
r1 = subprocess.run(['curl', '-sk', '-b', '/tmp/c.jar', '-c', '/tmp/c.jar', 'https://localhost:8081/'], capture_output=True, text=True, timeout=30)
# Test 1: /api/operations/32/update with valid JSON + CSRF
r2 = subprocess.run(['curl', '-sk', '-b', '/tmp/c.jar', '-X', 'POST', '-H', 'X-Requested-With: XMLHttpRequest', '-H', 'Content-Type: application/json', '-d', '{"field":"name","value":"test"}', '-w', '\\nHTTP=%{http_code}', 'https://localhost:8081/api/operations/32/update'], capture_output=True, text=True, timeout=30)
print('LOGIN_PAGE body (first 200):', r1.stdout[:200])
print()
print('Test 1 - valid JSON + CSRF:')
print('body:', r2.stdout)
print('stderr:', r2.stderr[:500])
# Test 2: check error log
r3 = subprocess.run(['tail', '-10', '/var/log/bit-technolog.err.log'], capture_output=True, text=True, timeout=30)
print()
print('Recent error log:')
print(r3.stdout)
"""
with sftp.file('/tmp/dbg.py', 'w') as f:
    f.write(test_py)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /tmp/dbg.py', timeout=60)
print('OUT:', stdout.read().decode()[:3000])
print('ERR:', stderr.read().decode()[:500])
client.close()
