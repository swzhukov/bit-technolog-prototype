import paramiko
import os
import subprocess
import json
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

# Direct on server
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
sftp = client.open_sftp()
test_py = '''
import subprocess, json
subprocess.run(['rm', '-f', '/tmp/c.jar'], check=False)
subprocess.run(['curl', '-sk', '-c', '/tmp/c.jar', '-X', 'POST', '-d', 'username=techadmin&password=demo', 'https://localhost:8081/login'], capture_output=True, timeout=30)

# Mimic my test - the exact same command construction
cmd = ['curl', '-sk', '-b', '/tmp/c.jar', '-X', 'POST', '-o', '/dev/null', '-w', '%{http_code}']
body = {"field":"name","value":"test"}
cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '-H', 'Content-Type: application/json', '-d', json.dumps(body)]
cmd.append('https://localhost:8081/api/operations/32/update')

print('cmd:', ' '.join(cmd))
r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
print('stdout:', r.stdout)
print('stderr:', r.stderr[:500])
'''
with sftp.file('/tmp/dbg2.py', 'w') as f:
    f.write(test_py)
sftp.close()
stdin, stdout, stderr = client.exec_command('python3 /tmp/dbg2.py', timeout=15)
print('OUT:', stdout.read().decode()[:2000])
client.close()
