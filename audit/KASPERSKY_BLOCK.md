# 🛡️ KASPERSKY ENDPOINT SECURITY блокирует наш prod (2026-07-23)

## Симптомы
- ERR_CONNECTION_RESET в браузере
- Title страницы = "Kaspersky Endpoint Security для Windows"  
- Toolbar: иконка "очки" = Kaspersky Protection активна
- В адресной строке: URL заменён на 217.114.7.5:8081 (Kaspersky перехватывает)
- В Console DevTools: `net::ERR_CONNECTION_RESET`

## Причина
Kaspersky Endpoint Security → **Web Protection** (Анти-Фишинг):
1. Перехватывает HTTP/HTTPS на нестандартных портах (8081, 8082, 8443)
2. Проверяет репутацию IP/порта
3. RST-ит TCP-соединение
4. Показывает свою защитную страницу

## Решение 1 (быстрое): добавить в исключения
**Kaspersky → Настройка → Защита → Веб-Защита → Настройка → Доверенные веб-адреса:**
```
https://217.114.7.5:8081/*
http://217.114.7.5:8082/*
```

## Решение 2 (временно): пауза защиты
**Kaspersky → Пауза защиты → 30 мин** → зайти на URL

## Решение 3 (надёжное): стандартный 443 через traefik
- URL: `https://seefeesnahurid.beget.app/bit-technolog/`
- Валидный Let's Encrypt (не самоподписанный)
- Стандартный порт 443 (Kaspersky не режет)

## Урок (Sprint 6+, pенa)
- Нестандартные порты → корп-антивирусы блокируют
- Production = стандартный 443 + домен
- Self-signed cert + alt-http = сразу несколько корп-проблем
