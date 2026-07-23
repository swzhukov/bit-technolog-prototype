import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
ls /opt/beget/ | grep -i "bit-technolog"
ls /opt/beget/bit-technolog-v0.7-backup/ 2>&1 | head -5
ls /opt/beget/bit-technolog-v0.7-backup/venv/bin/ 2>&1 | head -3
''', timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
