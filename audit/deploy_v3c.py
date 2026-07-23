import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
# Удалить venv и certs (если deleted), затем пересоздать
git checkout -- venv 2>&1
git clean -fd venv certs 2>&1 | tail -3
ls venv/bin/uvicorn 2>&1
ls certs/ 2>&1 | head -3
# Restart
rm -f __pycache__/app.cpython-312.pyc
pkill -9 -f "uvicorn app:app" 2>&1
sleep 2
systemctl reset-failed bit-technolog
systemctl start bit-technolog
sleep 4
curl -sk https://localhost:8081/health
''', timeout=60)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
