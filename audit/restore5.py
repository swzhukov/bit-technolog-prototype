import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('systemctl status bit-technolog | head -20; echo "---"; tail -30 /var/log/bit-technolog.err.log', timeout=30)
print('OUT:', stdout.read().decode()[:3000])
print('ERR:', stderr.read().decode()[:500])
client.close()
