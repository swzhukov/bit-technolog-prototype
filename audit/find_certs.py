import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
find / -name "cert.pem" 2>/dev/null | head -10
find / -name "key.pem" 2>/dev/null | head -10
''', timeout=60)
print('OUT:', stdout.read().decode()[:2000])
client.close()
