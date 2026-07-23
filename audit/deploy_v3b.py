import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
cd /opt/beget/bit-technolog
git status
# Если есть untracked - не критично
ls certs 2>&1 | head -2
ls venv/bin/uvicorn 2>&1
# Stash pop если был
git stash list
# Reset hard нельзя, потому что есть untracked
git fetch origin
git reset --hard origin/main 2>&1 | tail -3
ls certs 2>&1 | head -2
ls venv/bin/uvicorn 2>&1
''', timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
