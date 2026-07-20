"""
Ручная проверка: каждая из 7 ролей — что видит в header, на главной, на карточке.
Имитация глазами пользователя.
"""
import os
os.environ["PILOT_AUTH_DISABLED"] = "true"
os.environ["PILOT_RATELIMIT_DISABLED"] = "true"
os.environ["PILOT_CSRF_DISABLED"] = "true"
os.environ["DEMO_MODE"] = "true"

import sys, re
sys.path.insert(0, os.path.dirname(__file__))
import app as app_module
app_module.init_db()
from fastapi.testclient import TestClient

ROLES = {
    "technologist": ("👨‍🔧", "Технолог", "#2563eb"),
    "main_technologist": ("👑", "Гл. технолог", "#7c3aed"),
    "admin": ("🛡", "Админ", "#dc2626"),
    "normirovshchik": ("📏", "Нормировщик", "#0891b2"),
    "workshop_chief": ("🏭", "Нач. цеха", "#ea580c"),
    "constructor": ("📐", "Конструктор", "#16a34a"),
    "quality": ("🔍", "ОТК", "#db2777"),
}

def extract_badge(html):
    """Извлечь badge роли из header"""
    m = re.search(r'id="current-role-badge"[^>]*data-role="(\w+)"[^>]*style="background:\s*(\#[0-9a-fA-F]+)', html)
    if m:
        return m.group(1), m.group(2)
    return None, None

def extract_visible_admin(html):
    """Видны ли admin ссылки в header"""
    return 'href="/admin"' in html and 'href="/admin/settings"' in html

def extract_ai_block(html):
    """Виден ли AI-блок на карточке"""
    return "🤔 Уточнить" in html

def extract_approve_button(html):
    """Видны ли кнопки утверждения (вне скрытого модала)"""
    # Кнопка "Утвердить как главный" в action-bar
    return "Утвердить как гл" in html or "Утвердить как нач" in html

def extract_approve_chief_button(html):
    return "Утвердить как главный технолог" in html or "Утвердить как начальник цеха" in html

def extract_reopen_button(html):
    return "Вернуть в работу" in html

def check_role(c, role_code, role_name, role_color):
    print(f"\n{'='*70}")
    print(f"  Роль: {role_code} ({role_name})")
    print('='*70)

    # Switch role
    r = c.post("/api/role/switch", data={"role": role_code})
    assert r.status_code == 200

    # 1. Главная
    r = c.get("/")
    assert r.status_code == 200
    badge_role, badge_color = extract_badge(r.text)
    print(f"  Главная: badge={badge_role}, color={badge_color}")
    assert badge_role == role_code, f"❌ badge показывает {badge_role}, а должна {role_code}"
    assert role_color.lower() in badge_color.lower(), f"❌ цвет {badge_color} не совпадает с ожидаемым {role_color}"
    print(f"  ✅ Badge корректный: {badge_role} / {badge_color}")

    # 2. Видны ли admin-ссылки
    admin_visible = extract_visible_admin(r.text)
    if role_code == "admin":
        assert admin_visible, "❌ admin не видит admin-ссылки"
        print(f"  ✅ Admin-ссылки видны (как и должно)")
    else:
        assert not admin_visible, f"❌ {role_code} видит admin-ссылки (НЕ должно быть!)"
        print(f"  ✅ Admin-ссылки скрыты")

    # 3. Quick role buttons — выделена текущая
    m = re.search(r'class="quick-role-btn" data-role="(\w+)"[^>]*style="[^"]*background:\s*(#[0-9a-fA-F]+)', r.text)
    if m:
        print(f"  ✅ Quick-role кнопки на главной: первая = {m.group(1)}, цвет = {m.group(2)}")

    # 4. Найти первую деталь
    r = c.get("/")
    ids = re.findall(r'/detail/([\w\-]+)', r.text)
    if not ids:
        print("  ⚠ Нет деталей — пропускаю проверку карточки")
        return True
    did = ids[0]
    r = c.get(f"/detail/{did}")
    assert r.status_code == 200

    # 5. AI-блок
    ai_visible = extract_ai_block(r.text)
    if role_code in ("technologist", "main_technologist", "admin"):
        assert ai_visible, f"❌ {role_code} НЕ видит AI-блок (а должен)"
        print(f"  ✅ AI-блок виден (правильно)")
    else:
        assert not ai_visible, f"❌ {role_code} видит AI-блок (НЕ должно быть!)"
        print(f"  ✅ AI-блок скрыт (правильно)")

    # 6. Approve buttons
    if role_code in ("main_technologist", "workshop_chief", "admin"):
        if extract_approve_chief_button(r.text):
            print(f"  ✅ Кнопка 'Утвердить как главный' видна")
    elif role_code in ("technologist", "normirovshchik", "quality", "constructor"):
        # Технолог НЕ видит approve-chief (только гл.технолог/нач.цеха/админ)
        if role_code != "technologist":
            assert not extract_approve_chief_button(r.text), f"❌ {role_code} видит approve-chief"
            print(f"  ✅ Кнопка 'Утвердить как главный' скрыта")

    # 7. Reopen
    if role_code in ("technologist", "main_technologist", "admin"):
        # Эти роли могут вернуть в работу
        pass

    # 8. Admin endpoint
    r_admin = c.get("/admin")
    if role_code == "admin":
        assert r_admin.status_code == 200, f"❌ admin не может открыть /admin"
        print(f"  ✅ /admin доступен (200)")
    else:
        assert r_admin.status_code == 403, f"❌ {role_code} может открыть /admin (status={r_admin.status_code})"
        print(f"  ✅ /admin → 403 (правильно)")

    return True

def main():
    c = TestClient(app_module.app)

    # Создать хотя бы одну деталь для теста
    c.post("/api/role/switch", data={"role": "technologist"})
    c.post("/api/details",
        data={"designation": "CHECK-001", "name": "Check test",
              "model": "АЦ-6,0-40", "chassis": "КАМАЗ-43118",
              "material": "Сталь 09Г2С", "size_mm": "100", "mass_kg": "5",
              "surface_treatment": "Грунт ГФ-021"},
        follow_redirects=False)

    print("\n" + "#"*70)
    print("#  ПРОВЕРКА ВСЕХ 7 РОЛЕЙ — ЧТО ВИДИТ КАЖДАЯ")
    print("#"*70)

    ok = 0
    failed = 0
    for code, (icon, name, color) in ROLES.items():
        try:
            check_role(c, code, name, color)
            ok += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1

    print("\n" + "="*70)
    print(f"  ИТОГ: {ok} ролей OK, {failed} провалилось из 7")
    print("="*70)
    return failed == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
