import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
# Удалить certs symlink и создать нормальную директорию
ls -la certs
file certs
rm -rf certs
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=217.114.7.5" 2>&1 | tail -1
ls -la certs/
systemctl reset-failed bit-technolog
systemctl restart bit-technolog
sleep 5
systemctl status bit-technolog | head -5
''', timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
