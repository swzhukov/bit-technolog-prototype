"""Test runner для 42 тест-кейсов + RBAC matrix с fresh login."""
import paramiko, os, json, time, urllib.parse
BEGET = os.environ.get('BEGET_SSH_PASSWORD', '')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('seefeesnahurid.beget.app', username='root', password=BEGET, timeout=30)


def ssh_exec(cmd, timeout=15):
    """Execute shell command on prod."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()


def curl(method, path, user=None, form_data=None, json_data=None, hdr=None, timeout=15):
    """Run curl on prod. Returns HTTP code or -1 on error."""
    cmd = ['curl', '-sk', '-m', str(timeout), '-X', method, '-o', '/dev/null', '-w', '%{http_code}']
    if user:
        cmd += ['-b', f'/tmp/c-{user}.jar']
    if json_data is not None:
        body_s = json.dumps(json_data, ensure_ascii=False) if not isinstance(json_data, str) else json_data
        ssh_exec(f"printf '%s' '{body_s}' > /tmp/body.json")
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
        return int(out.split()[0])
    except:
        return -1


def login(user):
    """Fresh login for user (remove old cookies)."""
    ssh_exec(f"rm -f /tmp/c-{user}.jar; curl -sk -c /tmp/c-{user}.jar -X POST -d 'username={user}&password=demo' https://localhost:8081/login -o /dev/null")


USERS = ['techadmin', 'vorobyev', 'tarrietsky', 'golubev']
for u in USERS:
    login(u)

# Тесты
TESTS = [
    ('A01', 'Создание детали', 'POST', '/details/new', 303, 'tarrietsky', None,
     {'designation': f'TEST-A01-{int(time.time())}', 'name': 'A01', 'level': 'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('A02', 'Создание минимальное', 'POST', '/details/new', 303, 'tarrietsky', None,
     {'designation': f'TEST-A02-{int(time.time())}', 'name': 'A02', 'level': 'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('A05', 'Inline-edit name', 'POST', '/api/operations/32/update', 200, 'tarrietsky',
     {'field':'name','value':'T01_A05'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('A06', 'Inline-edit time', 'POST', '/api/operations/32/update', 200, 'tarrietsky',
     {'field':'time_per_unit_min','value':'15.5'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('A08', 'Подтвердить норму', 'POST', '/api/operations/32/confirm', 200, 'tarrietsky',
     {'new_time': 12.0}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('A10', 'Экспорт РС в 1С', 'POST', '/api/items/3/export-to-1c', 200, 'tarrietsky', None, None,
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('A11', 'Скачать XML РС', 'GET', '/api/rs/download/RS_ЛМША.301314.010_0002.xml', 200, 'tarrietsky', None, None, None),
    ('A12', 'Создание извещения', 'POST', '/notices/new', 303, 'tarrietsky', None,
     {'number': f'И-A12-{int(time.time())}', 'date':'2026-07-23','reason':'A12 test','affected_item_designation':'ЛМША.301314.010'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('A13', 'С предзаполнением', 'GET', '/notices/new?item_id=3', 200, 'tarrietsky', None, None, None),
    ('A15', 'Решение Принять AI', 'POST', '/api/change-notices/1/process', 200, 'tarrietsky',
     {'decision':'accept_ai'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('A16', 'Решение Ручная', 'POST', '/api/change-notices/1/process', 200, 'tarrietsky',
     {'decision':'manual_review'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('A17', 'Решение Отклонить', 'POST', '/api/change-notices/1/process', 200, 'tarrietsky',
     {'decision':'reject'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('B04', 'material_id 99999', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation': f'TEST-B04-{int(time.time())}', 'name':'B04', 'level':'detail', 'material_id':'99999'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('B08', 'Дубликат обозначения', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation':'ЛМША.301314.010', 'name':'Dup', 'level':'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('B09', 'mass_kg=abc', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation': f'TEST-B09-{int(time.time())}', 'name':'B09', 'level':'detail', 'mass_kg':'abc'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('B10', 'level=invalid', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation': f'TEST-B10-{int(time.time())}', 'name':'B10', 'level':'invalid'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('B12', 'Approve от technologist', 'POST', '/api/tech-cards/1/approve', 403, 'tarrietsky',
     {}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('B14', 'CSRF bypass', 'POST', '/api/operations/32/update', 403, 'tarrietsky',
     {'field':'name','value':'csrf'}, None, {'Content-Type': 'application/json'}),
    ('B15', 'Invalid JSON', 'POST', '/api/operations/32/update', 400, 'tarrietsky', None,
     {'input':'notjson'}, {'X-Requested-With': 'XMLHttpRequest'}),
    ('B16', '/notices/999/resolve', 'POST', '/notices/999/resolve', 404, 'tarrietsky', None,
     {'decision':'manual_review'}, {'X-Requested-With': 'XMLHttpRequest'}),
    ('B17', '/api/operations/99999/confirm', 'POST', '/api/operations/99999/confirm', 404, 'tarrietsky',
     {'new_time':5.0}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('B18', 'Logout', 'GET', '/logout', 303, 'techadmin', None, None, None),
    ('B19', 'Пустое designation', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation':'', 'name':'B19', 'level':'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('B20', 'Пустое name', 'POST', '/details/new', 400, 'tarrietsky', None,
     {'designation': f'TEST-B20-{int(time.time())}', 'name':'', 'level':'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('C01', 'Дашборд', 'GET', '/', 200, 'tarrietsky', None, None, None),
    ('C02', '/products', 'GET', '/products', 200, 'tarrietsky', None, None, None),
    ('C03', '/products?level=detail', 'GET', '/products?level=detail', 200, 'tarrietsky', None, None, None),
    ('C04', '/products?q=ЛМША', 'GET', '/products?q=%D0%9B%D0%9C%D0%A8%D0%90', 200, 'tarrietsky', None, None, None),
    ('C05', '/knowledge', 'GET', '/knowledge', 200, 'tarrietsky', None, None, None),
    ('C06', '/help', 'GET', '/help', 200, 'tarrietsky', None, None, None),
    ('C07', '/rs', 'GET', '/rs', 200, 'tarrietsky', None, None, None),
    ('C09', 'Не залогинен /detail/3', 'GET', '/detail/3', 303, None, None, None, None),
]

RBAC_TESTS = [
    ('RBAC-01', 'Создание детали', 'POST', '/details/new',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     None, lambda u='x': {'designation': f'RBAC-{int(time.time()*1000)}-{u[:3]}', 'name': 'R', 'level': 'detail'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-02', 'Inline-edit', 'POST', '/api/operations/32/update',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     {'field':'name','value':'rbac'}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-03', 'Approve ТК', 'POST', '/api/tech-cards/1/approve',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 403, 'golubev': 403},
     {}, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-04', 'Экспорт РС', 'POST', '/api/items/3/export-to-1c',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     None, None, {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-05', 'Создание извещения', 'POST', '/notices/new',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     None, lambda u='x': {'number': f'И-RBAC-{int(time.time()*1000)}-{u[:3]}', 'date':'2026-07-23','reason':'r','affected_item_designation':'ЛМША.301314.010'},
     {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-06', 'Решение по извещению', 'POST', '/notices/1/resolve',
     {'techadmin': 303, 'vorobyev': 303, 'tarrietsky': 303, 'golubev': 403},
     None, lambda: {'decision':'manual_review'}, {'X-Requested-With': 'XMLHttpRequest'}),
    ('RBAC-07', 'AI diff извещения', 'POST', '/notices/1/generate-diff',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 403},
     None, None, {'X-Requested-With': 'XMLHttpRequest'}, 60),
    ('RBAC-08', '/knowledge все', 'GET', '/knowledge',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 200}, None, None, None),
    ('RBAC-09', '/rs все', 'GET', '/rs',
     {'techadmin': 200, 'vorobyev': 200, 'tarrietsky': 200, 'golubev': 200}, None, None, None),
]

SKIP = {'A03','A04','A07','A09','A14','B01','B02','B03','B06','B07','B11','B13','C08','C10'}

RESULTS = []
def record(tid, name, expected, got, status, comment=''):
    sym = {'pass':'✅', 'fail':'❌', 'skip':'⏭'}
    RESULTS.append({'id':tid,'name':name,'expected':expected,'got':got,'status':status,'comment':comment})
    print(f"  {sym.get(status,'?')} {tid}: {name[:50]:50} exp={expected} got={got}")

print("="*60)
print("RUNNING TESTS (A/B/C) — A=прямые, B=отклонения, C=сервисные")
print("="*60)
print("\n--- A+B+C ---")
for tid, name, method, path, expected, user, json_d, form_d, hdr in TESTS:
    if user is not None:
        login(user)  # FRESH login
    code = curl(method, path, user=user, json_data=json_d, form_data=form_d, hdr=hdr)
    if tid in SKIP:
        record(tid, name, expected, code, 'skip')
    else:
        record(tid, name, expected, code, 'pass' if code == expected else 'fail')

print("\n--- RBAC (fresh login per user) ---")
for rbac_t in RBAC_TESTS:
    if len(rbac_t) == 9:
        tid, name, method, path, exp_map, json_d, form_d, hdr, custom_timeout = rbac_t
    else:
        tid, name, method, path, exp_map, json_d, form_d, hdr = rbac_t
        custom_timeout = 15
    results_per_user = {}
    ok = True
    for u in USERS:
        # Если form_d - lambda, вызываем для КАЖДОГО пользователя (свежее designation/number)
        if callable(form_d):
            try:
                fd = form_d(u)  # Передаём user для уникальности
            except TypeError:
                fd = form_d()
        else:
            fd = form_d
        login(u)  # FRESH login per user
        # custom_timeout уже в переменной
        c = curl(method, path, user=u, json_data=json_d, form_data=fd, hdr=hdr, timeout=custom_timeout)
        results_per_user[u] = c
        if c != exp_map[u]:
            ok = False
    exp_str = '|'.join(f"{u[:3]}:{exp_map[u]}" for u in USERS)
    got_str = '|'.join(f"{u[:3]}:{results_per_user[u]}" for u in USERS)
    record(tid, name, exp_str, got_str, 'pass' if ok else 'fail')

print("\n--- SMOKE ---")
login('tarrietsky')
smoke_results = []
for endpoint, expected in [
    ('/', 200), ('/products', 200), ('/detail/3', 200), ('/notices', 200),
    ('/knowledge', 200), ('/help', 200), ('/rs', 200),
]:
    c = curl('GET', endpoint, user='tarrietsky')
    smoke_results.append((endpoint, expected, c))
all_ok = all(c == e for _, e, c in smoke_results)
record('SMOKE', 'Smoke test 7 endpoints', 'all 200', str([(e, c) for e, _, c in smoke_results])[:120], 'pass' if all_ok else 'fail')

# Cleanup
ssh_exec('''python3 -c "
import sqlite3
c = sqlite3.connect('data/bit_technolog_v0_8.db')
c.execute(\"DELETE FROM items WHERE designation LIKE 'TEST-%' OR designation LIKE 'RBAC-%'\")
c.execute(\"DELETE FROM history WHERE details_json LIKE '%TEST-%' OR details_json LIKE '%RBAC-%'\")
c.execute(\"DELETE FROM change_notices WHERE number LIKE 'И-A12-%' OR number LIKE 'И-RBAC-%'\")
c.commit()
print('cleaned')
" ''')
client.close()

n_pass = sum(1 for r in RESULTS if r['status'] == 'pass')
n_fail = sum(1 for r in RESULTS if r['status'] == 'fail')
n_skip = sum(1 for r in RESULTS if r['status'] == 'skip')
print(f"\n{'='*60}")
print(f"ИТОГО: {len(RESULTS)} (✅{n_pass} ❌{n_fail} ⏭{n_skip})")
bugs = [r for r in RESULTS if r['status'] == 'fail']
if bugs:
    print(f"\n❌ FAILED ({len(bugs)}):")
    for b in bugs:
        print(f"   {b['id']}: {b['name']} - exp={b['expected']} got={b['got']}")
with open('/workspace/bit-technolog-prototype/audit/TEST_RESULTS.json', 'w') as f:
    json.dump(RESULTS, f, indent=2, ensure_ascii=False)
