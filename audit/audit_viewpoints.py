"""5 viewpoints глубокий анализ."""
import os
import re

# View 1: Цели/ценности (152-ФЗ, терминология)
print("=== VIEWPOINT 1: ЦЕЛИ/ЦЕННОСТИ===")
with open('/workspace/bit-technolog-prototype/templates/base.html') as f:
    base = f.read()
# 152-ФЗ
if "Добрый день, коллега" in base or "Добрый день" in base:
    print("  ✅ 152-ФЗ: 'Добрый день' generic")
else:
    print("  ⚠ 152-ФЗ: greeting не generic")
# Терминология
bad_words = ['JSON', 'API endpoint', 'GET ', 'POST ', 'REST']
with open('/workspace/bit-technolog-prototype/templates/dashboard.html') as f:
    dash = f.read()
for w in bad_words:
    if w in dash:
        print(f"  ⚠ Терминология: '{w}' в dashboard.html (не для технолога)")

# View 2: Концепции
print()
print("=== VIEWPOINT 2: КОНЦЕПЦИИ===")
with open('/workspace/bit-technolog-prototype/app.py') as f:
    app = f.read()
# LLMProvider интерфейс
if "class LLMProvider" in app or "LLMProvider" in app:
    print("  ✅ LLMProvider интерфейс")
# OneCGateway
if "class OneCGateway" in app or "OneCGateway" in app:
    print("  ✅ OneCGateway интерфейс")
# RAG
if "rag" in app.lower():
    print("  ✅ RAG (services/rag.py)")
# ref_1c
if "ref_1c" in app:
    print("  ✅ ref_1c в коде")

# View 3: Реализация
print()
print("=== VIEWPOINT 3: РЕАЛИЗАЦИЯ===")
# N+1
# Смотрю db.query в цикле
n_plus_1 = 0
for m in re.finditer(r'for .* in .*:\n.*db\.query', app):
    n_plus_1 += 1
print(f"  N+1 candidates: {n_plus_1}")
# SQL injection
sql_inj = re.findall(r'execute\(["\'][^"\']*%s', app)
if sql_inj:
    print(f"  ⚠ SQL injection patterns: {len(sql_inj)}")
else:
    print("  ✅ Нет SQL injection (все ? placeholders)")

# View 4: UX
print()
print("=== VIEWPOINT 4: UX===")
# Каждый template — есть ли пустая страница?
for tmpl in os.listdir('/workspace/bit-technolog-prototype/templates'):
    if tmpl.endswith('.html'):
        path = f'/workspace/bit-technolog-prototype/templates/{tmpl}'
        with open(path) as f:
            content = f.read()
        if '{% extends "base.html" %}' not in content and tmpl != 'base.html':
            print(f"  ⚠ {tmpl}: не extends base.html")

# View 5: Эксплуатация
print()
print("=== VIEWPOINT 5: ЭКСПЛУАТАЦИЯ===")
# Health endpoint
r = subprocess.run(['curl', '-sk', '-w', '\nHTTP=%{http_code}', 'https://217.114.7.5:8081/health'], capture_output=True, text=True, timeout=15)
print(f"  /health: {r.stdout[:300]}")
