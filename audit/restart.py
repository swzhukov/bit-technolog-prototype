import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
ls venv/bin/uvicorn
systemctl reset-failed bit-technolog
systemctl restart bit-technolog
sleep 5
systemctl status bit-technolog | head -5
curl -sk https://localhost:8081/health -w "\\nHTTP=%{http_code}\\n"
''', timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
