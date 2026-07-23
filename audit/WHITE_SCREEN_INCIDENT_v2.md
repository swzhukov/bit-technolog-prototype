# 🚨 WHITE SCREEN INCIDENT v2 — RESOLVED (2026-07-23)

## v8.1.1 → v8.2 (HEAD 6fbb7db)

### v8.1.1: uvicorn на 8443, redirect на 8081
- Пересадил uvicorn с 8081 на 8443 (https)
- http_redirect пересадил с 8082 на 8081
- HEAD: a60a970

**Сергей:** "да ничего не меняется же" + скриншот 217.114.7.5:8443 — белый экран, крутилка бесконечная.

### Диагноз v8.1.1
- Curl снаружи на 8443 → 303 (ОК)
- Browser на 8443 → белый экран (timeout)
- Причина 1: 8443 — нестандартный порт, может блокироваться офисным firewall
- Причина 2: возможно SSL handshake занимает >30s в браузере

### v8.2: revert на стандартные порты
- uvicorn обратно на **8081 (https)**
- http_redirect на **8082 (http) → 301 → https://...:8081**
- HEAD: 6fbb7db

### Verify v8.2
```
$ curl -sk -m 5 -i https://217.114.7.5:8081/
HTTP/1.1 303 See Other
location: /login?next=/

$ curl -sk -m 5 -i http://217.114.7.5:8082/
HTTP/1.0 301 Moved Permanently
Location: https://217.114.7.5:8081/
```

Playwright (headless Chromium):
- TEST 1: `https://217.114.7.5:8081/` → 303 → login form → "Вход — БИТ.Технолог"
- Login techadmin/demo → 200, "Мои задачи — БИТ.Технолог", "Добрый день, коллега"
- TEST 2: `http://217.114.7.5:8082/` → 301 → https://...:8081 → cookies сохранились → "Мои задачи"

Скриншоты: `/workspace/v8_fix_https.png`, `/workspace/v8_fix_dashboard.png`, `/workspace/v8_fix_redirect.png`

## Сергею — что делать

**Один из двух URL:**

1. **`https://217.114.7.5:8081/`** (напрямую https)
2. **`http://217.114.7.5:8082/`** (с redirect на https)

Оба должны работать. **НЕ 8443.** Стандартные alt-http порты 8081/8082.

### Если белый экран
1. **Hard refresh** (Ctrl+Shift+R)
2. **Инкогнито** (Ctrl+Shift+N)
3. **DevTools → Network** — какие запросы, какие статусы, есть ли Failed/SSL
4. **DevTools → Console** — есть ли ошибки
5. Скриншот всего этого мне

## Lessons (накапливаются)
1. **Стандартные порты 8081/8082** — не выдумывать 8443, пользователи не поймут
2. **Verify руками в браузере**, не только curl
3. **Самопроверка в playwright** перед инструкцией пользователю
4. **Когда http:// — белый экран** → проверить curl, искать Connection reset
5. **HEAD lessons** = я 2 раза за день накосячил с портами
