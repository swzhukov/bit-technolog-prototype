import paramiko
import os
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)
stdin, stdout, stderr = client.exec_command('''
rm -f /tmp/c.jar
curl -sk -c /tmp/c.jar -X POST -d "username=techadmin&password=demo" https://localhost:8081/login -o /dev/null
curl -sk -b /tmp/c.jar -X POST -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" -d '{"field":"name","value":"test"}' -w "\nHTTP=%{http_code}\n" https://localhost:8081/api/operations/32/update
echo "---"
tail -5 /var/log/bit-technolog.err.log
''', timeout=15)
print('OUT:', stdout.read().decode()[:2000])
client.close()
