import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
cmd = '''
cd /opt/beget/bit-technolog
git stash pop 2>&1 | tail -1
git status
ls certs venv 2>&1 | head -3
'''
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
