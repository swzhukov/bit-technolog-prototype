import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
ls venv/bin/uvicorn 2>&1
ls venv/bin/python* 2>&1
# Попробовать запустить напрямую
ls -la /opt/beget/bit-technolog-v0.8.0-backup/venv/bin/uvicorn
''', timeout=30)
print('OUT:', stdout.read().decode()[:1500])
print('ERR:', stderr.read().decode()[:500])
client.close()
