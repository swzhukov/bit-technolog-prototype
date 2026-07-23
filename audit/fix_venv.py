import paramiko, os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
cmd = '''
cd /opt/beget/bit-technolog
rm -rf venv
# Recreate from system python
python3 -m venv venv 2>&1 | tail -3
source venv/bin/activate
pip install --quiet --no-cache-dir -r requirements.txt 2>&1 | tail -3
# Or use venv from backup if exists
ls venv/bin/uvicorn
'''
stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
print('OUT:', stdout.read().decode()[:3000])
print('ERR:', stderr.read().decode()[:500])
client.close()
