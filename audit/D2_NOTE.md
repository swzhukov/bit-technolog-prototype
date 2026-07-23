# D2: multi-worker (попытка)

**Попытка:** --workers 2 → uvicorn сразу killed (статус=9/KILL)

**Гипотезы:**
1. SSL port sharing — uvicorn workers могут конфликтовать на 8081
2. Memory limit — 2 workers × 35MB = 70MB > system limit
3. systemd StartLimitBurst — после серии kill срабатывает rate limit

**Решение:** оставил --workers 1 (предыдущее значение).
Shared state (D1) уже готов — когда вырастет нагрузка, легко переключить.

**Альтернатива:** запустить 2 копии uvicorn на разных портах + nginx upstream.
Но это не входит в текущий Sprint 6 (1 день на D2).

**Статус:** D2 частично — state готов, workers не масштабирован.
