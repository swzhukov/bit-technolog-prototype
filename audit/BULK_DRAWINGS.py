"""Bulk processing всех PDF/PNG чертежей через OCR+LLM.
Цель: оценить качество на реальных данных, выявить паттерны.

Использование:
  export BEGET_SSH_PASSWORD=...
  python3 audit/BULK_DRAWINGS.py
"""
import os, sys, json, time, subprocess
import urllib.request, urllib.parse
import http.cookiejar

BASE = 'https://seefeesnahurid.beget.app/bit-technolog'
SSH = 'seefeesnahurid.beget.app'

def login():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [('X-Requested-With', 'XMLHttpRequest')]
    data = urllib.parse.urlencode({'username': 'techadmin', 'password': 'demo'}).encode()
    opener.open(f'{BASE}/login', data=data, timeout=30)
    return cj, opener

def upload(opener, path):
    import mimetypes
    boundary = '----formboundary' + str(int(time.time()))
    fname = os.path.basename(path)
    with open(path, 'rb') as f:
        content = f.read()
    body = (f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'
            f'Content-Type: {mimetypes.guess_type(path)[0] or "application/octet-stream"}\r\n'
            f'\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(
        f'{BASE}/api/drawings/upload',
        data=body,
        method='POST',
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        }
    )
    try:
        resp = opener.open(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'body': e.read().decode()[:200]}

def process(opener, drawing_id, timeout=120):
    req = urllib.request.Request(
        f'{BASE}/api/drawings/{drawing_id}/process',
        method='POST',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    try:
        resp = opener.open(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'body': e.read().decode()[:200]}

def get(opener, drawing_id):
    resp = opener.open(f'{BASE}/api/drawings/{drawing_id}', timeout=15)
    return json.loads(resp.read().decode())

def ssh_ls(remote_dir):
    pw = os.environ.get('BEGET_SSH_PASSWORD', '')
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH, username='root', password=pw, timeout=20)
    i,o,e = c.exec_command(f'ls {remote_dir} 2>&1')
    files = [l.strip() for l in o.read().decode().split('\n') if l.strip()]
    c.close()
    return files

def main():
    # Получим список PDF
    print("=" * 70)
    print("BULK DRAWINGS PROCESSING — Sprint 7 Quality Test")
    print("=" * 70)
    
    files = ssh_ls('/opt/beget/bit-technolog/attachments')
    pdfs = [f for f in files if f.endswith('.pdf')]
    pngs = [f for f in files if f.endswith('.png') or f.endswith('.PNG')]
    print(f"\nFound: {len(pdfs)} PDF + {len(pngs)} PNG = {len(pdfs)+len(pngs)} drawings")
    print(f"\nWill process first 5 PDF for quality assessment (full = too long)\n")
    
    cj, opener = login()
    
    results = []
    for pdf in pdfs[:5]:
        remote_path = f'/opt/beget/bit-technolog/attachments/{pdf}'
        print(f"\n--- {pdf} ---")
        
        # Download to /tmp via sftp
        import paramiko
        pw = os.environ.get('BEGET_SSH_PASSWORD', '')
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(SSH, username='root', password=pw, timeout=20)
        sftp = c.open_sftp()
        local_path = f'/tmp/bulk_{pdf}'
        sftp.get(remote_path, local_path)
        sftp.close()
        c.close()
        print(f"  Downloaded: {os.path.getsize(local_path)} bytes")
        
        # Upload via API
        uploaded = upload(opener, local_path)
        if 'error' in uploaded:
            print(f"  ❌ Upload failed: {uploaded['error']}: {uploaded.get('body','')}")
            continue
        did = uploaded.get('id')
        print(f"  ✅ Uploaded, id={did}")
        
        # Process
        t0 = time.time()
        proc_result = process(opener, did, timeout=120)
        dt = time.time() - t0
        
        if 'error' in proc_result:
            print(f"  ❌ Process failed: {proc_result['error']}")
            continue
        
        # Get final state
        d = get(opener, did)
        llm = d.get('llm_extracted_json')
        if llm:
            try:
                llm_data = json.loads(llm)
            except:
                llm_data = {}
        else:
            llm_data = {}
        
        designation = llm_data.get('designation') or '-'
        name = llm_data.get('name') or '-'
        material = llm_data.get('material') or '-'
        gost = llm_data.get('gost') or '-'
        dimensions = llm_data.get('dimensions') or '-'
        
        print(f"  ⏱️  Process: {dt:.1f}s")
        print(f"  📋 OCR: {d.get('ocr_status')} ({d.get('ocr_duration_ms')}ms)")
        print(f"  📋 LLM: {d.get('llm_status')} ({d.get('llm_duration_ms')}ms)")
        print(f"  📝 Designation: {designation}")
        print(f"  📝 Name: {name}")
        print(f"  📝 Material: {material}")
        print(f"  📝 GOST: {gost}")
        print(f"  📝 Dimensions: {dimensions}")
        
        results.append({
            'file': pdf,
            'process_time_sec': round(dt, 1),
            'designation': designation,
            'name': name,
            'material': material,
            'gost': gost,
            'dimensions': dimensions,
            'designation_filled': designation != '-',
            'name_filled': name != '-',
            'gost_filled': gost != '-',
        })
    
    # Save results
    out = '/workspace/bit-technolog-prototype/audit/BULK_DRAWINGS_RESULTS.json'
    with open(out, 'w') as f:
        json.dump({'date': '2026-07-23', 'count': len(results), 'results': results}, f, indent=2, ensure_ascii=False)
    print(f"\n\n{'=' * 70}")
    print(f"Results saved to {out}")
    print(f"\nQuality summary ({len(results)} drawings):")
    if results:
        desig_filled = sum(1 for r in results if r['designation_filled'])
        name_filled = sum(1 for r in results if r['name_filled'])
        gost_filled = sum(1 for r in results if r['gost_filled'])
        avg_time = sum(r['process_time_sec'] for r in results) / len(results)
        print(f"  Designation filled: {desig_filled}/{len(results)} ({100*desig_filled/len(results):.0f}%)")
        print(f"  Name filled: {name_filled}/{len(results)} ({100*name_filled/len(results):.0f}%)")
        print(f"  GOST filled: {gost_filled}/{len(results)} ({100*gost_filled/len(results):.0f}%)")
        print(f"  Avg process time: {avg_time:.1f}s")

if __name__ == '__main__':
    main()
