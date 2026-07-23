import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
./venv/bin/uvicorn app:app --host 0.0.0.0 --port 8081 --ssl-keyfile=certs/key.pem --ssl-certfile=certs/cert.pem 2>&1 | head -30
''', timeout=15)
print('OUT:', stdout.read().decode()[:3000])
print('ERR:', stderr.read().decode()[:500])
client.close()
