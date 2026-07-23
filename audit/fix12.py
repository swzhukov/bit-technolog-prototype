import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
# Подождать чтобы restart counter сбросился
sleep 30
# Reset и start
systemctl reset-failed bit-technolog
systemctl start bit-technolog
sleep 5
systemctl status bit-technolog | head -5
curl -sk https://localhost:8081/health
''', timeout=90)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
