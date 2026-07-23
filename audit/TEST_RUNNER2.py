import paramiko, os, json, time
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)

# Helper: write JSON body to file, curl with --data-binary @file
def curl(client, method, path, user=None, json_data=None, form_data=None, hdr=None, timeout=15, expect_redirect=False):
    cmd = ['curl', '-sk', '-m', str(timeout), '-X', method, '-o', '/dev/null']
    if expect_redirect:
        cmd += ['-w', '%{http_code} %{redirect_url}']
    else:
        cmd += ['-w', '%{http_code}']
    if user:
        cmd += ['-b', f'/tmp/c-{user}.jar']
    if json_data is not None:
        # Write to file on server
        body_s = json.dumps(json_data, ensure_ascii=False) if not isinstance(json_data, str) else json_data
        client.exec_command(f"echo -n '{body_s}' > /tmp/body.json", timeout=5)
        cmd += ['-H', 'Content-Type: application/json', '-d', '@/tmp/body.json']
    elif form_data is not None:
        for k, v in form_data.items():
            cmd += ['--data-urlencode', f'{k}={v}']
    if hdr:
        for k, v in hdr.items():
            cmd += ['-H', f'{k}: {v}']
    cmd.append(f'https://localhost:8081{path}')
    cmd_str = ' '.join("'" + c + "'" if ' ' in c or '{' in c or '}' in c else c for c in cmd)
    stdin, stdout, stderr = client.exec_command(cmd_str, timeout=timeout+5)
    out = stdout.read().decode().strip()
    try:
        # Status может быть "303" или "303 https://..."
        code_s = out.split()[0]
        return int(code_s), out
    except:
        return -1, out

def login(client, user):
    client.exec_command(f"rm -f /tmp/c-{user}.jar; curl -sk -c /tmp/c-{user}.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null", timeout=15)

# Login 4 users
for u in ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']:
    login(client, u)

# Define all tests
TESTS = []

def t(tid, name, method, path, expected, user='tarrietsky', json_data=None, form_data=None, hdr=None):
    TESTS.append({'id': tid, 'name': name, 'method': method, 'path': path, 'expected': expected, 'user': user, 'json': json_data, 'form': form_data, 'hdr': hdr})

# A
t('A01', 'Создание детали', 'POST', '/details/new', 303,
  form_data={'designation': f'TEST-A01-{int(time.time())}', 'name': 'A01', 'level': 'detail'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('A02', 'Создание минимальное', 'POST', '/details/new', 303,
  form_data={'designation': f'TEST-A02-{int(time.time())}', 'name': 'A02', 'level': 'detail'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
# A03/A04/A07/A09/A14: skip (LLM/UI)
t('A05', 'Inline-edit name', 'POST', '/api/operations/32/update', 200,
  json_data={'field':'name','value':'T01_A05'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('A06', 'Inline-edit time', 'POST', '/api/operations/32/update', 200,
  json_data={'field':'time_per_unit_min','value':'15.5'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('A08', 'Подтвердить норму', 'POST', '/api/operations/32/confirm', 200,
  json_data={'new_time': 12.0},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('A10', 'Экспорт РС в 1С', 'POST', '/api/items/3/export-to-1c', 200, hdr={'X-Requested-With':'XMLHttpRequest'})
t('A11', 'Скачать XML РС', 'GET', '/api/rs/download/RS_ЛМША.301314.010_0002.xml', 200)
t('A12', 'Создание извещения', 'POST', '/notices/new', 303,
  form_data={'number': f'И-A12-{int(time.time())}', 'date':'2026-07-23','reason':'A12 test','affected_item_designation':'ЛМША.301314.010'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('A13', 'С предзаполнением', 'GET', '/notices/new?item_id=3', 200)
t('A15', 'Решение "Принять AI"', 'POST', '/api/change-notices/1/process', 200,
  json_data={'decision':'accept_ai'}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('A16', 'Решение "Ручная"', 'POST', '/api/change-notices/1/process', 200,
  json_data={'decision':'manual_review'}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('A17', 'Решение "Отклонить"', 'POST', '/api/change-notices/1/process', 200,
  json_data={'decision':'reject'}, hdr={'X-Requested-With':'XMLHttpRequest'})

# B
t('B04', 'material_id 99999', 'POST', '/details/new', 400,
  form_data={'designation': f'TEST-B04-{int(time.time())}', 'name':'B04', 'level':'detail', 'material_id':'99999'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('B08', 'Дубликат обозначения', 'POST', '/details/new', 400,
  form_data={'designation':'ЛМША.301314.010', 'name':'Dup', 'level':'detail'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('B09', 'mass_kg=abc', 'POST', '/details/new', 400,
  form_data={'designation': f'TEST-B09-{int(time.time())}', 'name':'B09', 'level':'detail', 'mass_kg':'abc'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('B10', 'level=invalid', 'POST', '/details/new', 400,
  form_data={'designation': f'TEST-B10-{int(time.time())}', 'name':'B10', 'level':'invalid'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('B12', 'Approve от technologist', 'POST', '/api/tech-cards/1/approve', 403,
  json_data={}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('B14', 'CSRF bypass', 'POST', '/api/operations/32/update', 403,
  json_data={'field':'name','value':'csrf'},
  hdr={'Content-Type':'application/json'})  # NO XRW
t('B15', 'Invalid JSON', 'POST', '/api/operations/32/update', 400,
  form_data={'input':'notjson'}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('B16', '/notices/999/resolve', 'POST', '/notices/999/resolve', 404,
  form_data={'decision':'manual_review'}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('B17', '/api/operations/99999/confirm', 'POST', '/api/operations/99999/confirm', 404,
  json_data={'new_time':5.0}, hdr={'X-Requested-With':'XMLHttpRequest'})
t('B18', 'Logout', 'GET', '/logout', 303, user='techadmin')
t('B19', 'Пустое designation', 'POST', '/details/new', 400,
  form_data={'designation':'', 'name':'B19', 'level':'detail'},
  hdr={'X-Requested-With':'XMLHttpRequest'})
t('B20', 'Пустое name', 'POST', '/details/new', 400,
  form_data={'designation': f'TEST-B20-{int(time.time())}', 'name':'', 'level':'detail'},
  hdr={'X-Requested-With':'XMLHttpRequest'})

# C
t('C01', 'Дашборд', 'GET', '/', 200)
t('C02', '/products', 'GET', '/products', 200)
t('C03', '/products?level=detail', 'GET', '/products?level=detail', 200)
t('C04', '/products?q=ЛМША', 'GET', '/products?q=%D0%9B%D0%9C%D0%A8%D0%90', 200)
t('C05', '/knowledge', 'GET', '/knowledge', 200)
t('C06', '/help', 'GET', '/help', 200)
t('C07', '/rs', 'GET', '/rs', 200)
# C08 = B18
# C09: NO cookies
t('C09', 'Не залогинен', 'GET', '/detail/3', 303, user=None)

# RBAC
RBAC_TESTS = [
    ('RBAC-01', 'Создание детали', 'POST', '/details/new',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     form_data_t={'designation': '__TIME__', 'name': 'RBAC', 'level': 'detail'},
     hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-02', 'Inline-edit', 'POST', '/api/operations/32/update',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     json_data_t={'field':'name','value':'rbac'},
     hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-03', 'Approve ТК', 'POST', '/api/tech-cards/1/approve',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 403, 'golubev': 403},
     json_data_t={}, hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-04', 'Экспорт РС', 'POST', '/api/items/3/export-to-1c',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-05', 'Создание извещения', 'POST', '/notices/new',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     form_data_t={'number': '__NUM__', 'date':'2026-07-23','reason':'rbac','affected_item_designation':'ЛМША.301314.010'},
     hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-06', 'Решение по извещению', 'POST', '/notices/1/resolve',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     form_data_t={'decision':'manual_review'}, hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-07', 'AI diff извещения', 'POST', '/notices/1/generate-diff',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     hdr={'X-Requested-With':'XMLHttpRequest'}),
    ('RBAC-08', '/knowledge все', 'GET', '/knowledge',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 200}, None, None),
    ('RBAC-09', '/rs все', 'GET', '/rs',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 200}, None, None),
]

# SMOKE
SMOKE = [
    ('/', 200), ('/products', 200), ('/detail/3', 200), ('/notices', 200),
    ('/knowledge', 200), ('/help', 200), ('/rs', 200),
]

# Run
RESULTS = []
def record(tid, name, expected, got, status, comment=''):
    sym = {'pass':'✅', 'fail':'❌', 'skip':'⏭'}
    RESULTS.append({'id':tid,'name':name,'expected':expected,'got':got,'status':status,'comment':comment})
    print(f"  {sym.get(status,'?')} {tid}: {name[:50]:50} exp={expected} got={got}")

print("="*60)
print("RUNNING TESTS")
print("="*60)

# Run TESTS
print("\n--- A: ПРЯМЫЕ ---")
for t_def in TESTS:
    code, raw = curl(client, t_def['method'], t_def['path'],
        user=t_def.get('user'),
        json_data=t_def.get('json'),
        form_data=t_def.get('form'),
        hdr=t_def.get('hdr'))
    expected = t_def['expected']
    status = 'pass' if code == expected else 'fail'
    if t_def['id'] in ('A03','A04','A07','A09','A14','B01','B02','B03','B07','B11','B13','C10'):
        status = 'skip'
    record(t_def['id'], t_def['name'], expected, code, status)

# Run RBAC
print("\n--- RBAC ---")
for rbac_t in RBAC_TESTS:
    tid, name, method, path, exp_map, *rest = rbac_t
    json_data_t = None
    form_data_t = None
    hdr = None
    if len(rest) >= 1 and rest[0] is not None:
        if 'form' in str(type(rest[0])):
            form_data_t = rest[0]
        else:
            json_data_t = rest[0]
    if len(rest) >= 2: hdr = rest[1] if len(rest) > 1 else None
    # Parse args - it's a tuple
    json_t = None
    form_t = None
    hdr = None
    if 'json_data_t' in rbac_t[5] if len(rbac_t) > 5 else {}:
        pass
    # Simpler: parse the rbac_t tuple manually
    # rbac_t: (tid, name, method, path, exp_map, json_or_form_dict, hdr)
    json_or_form = rbac_t[5] if len(rbac_t) > 5 else None
    hdr = rbac_t[6] if len(rbac_t) > 6 else None
    # Detect: dict with 'field' or 'new_time' = json
    if json_or_form and ('field' in str(json_or_form) or 'new_time' in str(json_or_form) or 'decision' in str(json_or_form)):
        json_t = json_or_form
    elif json_or_form and ('designation' in str(json_or_form) or 'number' in str(json_or_form)):
        form_t = json_or_form.copy() if json_or_form else {}
        if form_t and 'designation' in form_t:
            form_t['designation'] = f'RBAC-{int(time.time())}'
        if form_t and 'number' in form_t:
            form_t['number'] = f'И-RBAC-{int(time.time())}'
    results_per_user = {}
    ok = True
    for u in USERS:
        login(client, u)  # Re-login to ensure fresh cookies
        c, _ = curl(client, method, path, user=u, json_data=json_t, form_data=form_t, hdr=hdr)
        results_per_user[u] = c
        if c != exp_map[u]:
            ok = False
    exp_str = '|'.join(f"{u[:3]}:{exp_map[u]}" for u in USERS)
    got_str = '|'.join(f"{u[:3]}:{results_per_user[u]}" for u in USERS)
    record(tid, name, exp_str, got_str, 'pass' if ok else 'fail')

# SMOKE
print("\n--- SMOKE ---")
login(client, 'tarrietsky')
smoke_results = []
for endpoint, expected in SMOKE:
    c, _ = curl(client, 'GET', endpoint, user='tarrietsky')
    smoke_results.append((endpoint, expected, c))
all_ok = all(c == e for _, e, c in smoke_results)
record('SMOKE', 'Smoke test 7 endpoints', 'all 200', str(smoke_results)[:80], 'pass' if all_ok else 'fail')

# Cleanup
client.exec_command("""python3 -c "
import sqlite3
c = sqlite3.connect('data/bit_technolog_v0_8.db')
c.execute(\"DELETE FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%'\")
c.execute(\"DELETE FROM history WHERE details_json LIKE '%TEST-%' OR details_json LIKE '%RBAC-%'\")
c.execute(\"DELETE FROM change_notices WHERE number LIKE 'И-A12-%' OR number LIKE 'И-RBAC-%'\")
c.commit()
print('cleaned')
" """, timeout=15)
client.close()

# Stats
n_pass = sum(1 for r in RESULTS if r['status'] == 'pass')
n_fail = sum(1 for r in RESULTS if r['status'] == 'fail')
n_skip = sum(1 for r in RESULTS if r['status'] == 'skip')
print(f"\n{'='*60}")
print(f"ИТОГО: {len(RESULTS)} (✅{n_pass} ❌{n_fail} ⏭{n_skip})")

with open('/workspace/audit/TEST_RESULTS.json', 'w') as f:
    json.dump(RESULTS, f, indent=2, ensure_ascii=False)
