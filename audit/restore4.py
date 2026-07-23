import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
cmd = '''
cd /opt/beget/bit-technolog
rm -rf venv
cp -a /opt/beget/bit-technolog-v0.8.0-backup/venv . 2>&1
ls venv/bin/uvicorn
# Restart
pkill -9 -f "uvicorn app:app" 2>&1
sleep 2
systemctl reset-failed bit-technolog
systemctl start bit-technolog
sleep 5
systemctl status bit-technolog | head -5
'''
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
