import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
cmd = '''
cd /opt/beget/bit-technolog
# Pull rebase (теперь без изменений)
git pull --rebase origin main 2>&1 | tail -3
# certs восстановил? нет
ls certs 2>&1
# regen
rm -rf certs
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=217.114.7.5" 2>&1 | tail -1
ls certs/
# restart
rm -f __pycache__/app.cpython-312.pyc
pkill -9 -f "uvicorn app:app" 2>&1
sleep 2
systemctl reset-failed bit-technolog
systemctl start bit-technolog
sleep 5
curl -sk https://localhost:8081/health -w "\\nHTTP=%{http_code}\\n"
'''
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
