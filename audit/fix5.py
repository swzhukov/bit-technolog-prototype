import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
cat requirements.txt
echo "---"
# Установить uvicorn отдельно
source venv/bin/activate
pip install uvicorn[standard] 2>&1 | tail -3
ls venv/bin/uvicorn
# restart
pkill -9 -f "uvicorn app:app" 2>&1
sleep 2
systemctl reset-failed bit-technolog
systemctl start bit-technolog
sleep 4
curl -sk https://localhost:8081/health
''', timeout=120)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
