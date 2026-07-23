import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
cmd = '''
cd /opt/beget/bit-technolog
ls -la venv
rm -rf venv
# Попробуем скопировать системный python
mkdir -p venv
# Используем /usr/bin/python3 напрямую
which python3
which pip
# Скопируем минимально: app.py может работать на системном python
systemctl show bit-technolog | grep ExecStart
'''
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
print('OUT:', stdout.read().decode()[:2000])
print('ERR:', stderr.read().decode()[:500])
client.close()
