import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('ps -ef | grep uvicorn | head -5; systemctl status bit-technolog | head -3; curl -sk https://localhost:8081/health 2>&1', timeout=15)
print('OUT:', stdout.read().decode()[:2000])
client.close()
