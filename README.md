# БИТ.Технолог — Прототип v0.1

AI-помощник технолога для ускорения создания техкарт в 1С:ERP.

**Пилотный клиент:** ООО «ПК Техинком-Центр» (пожарная спецтехника).

## Что это

- Принимает свойства деталей (mock — имитация КОМПАС-3D)
- Генерирует черновик техкарты через LLM (1bitai.ru / DeepSeek / OpenAI-совместимый)
- Показывает 6 вкладок: Сводка / Маршрут / Операции / Обоснование / Warnings / Вопросы
- Позволяет технологу утвердить или отклонить
- Экспортирует в Excel и PDF

## Установка (Windows)

```powershell
cd C:\Projects\MiniMax\BIT_Tech\bit-technolog-prototype
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe app.py
```

Открыть http://localhost:8080

## Обновление

```powershell
git pull
# если менялся requirements.txt:
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Стек

- Python 3.11+
- FastAPI + Jinja2 + HTMX
- SQLite (встроенная)
- openai SDK (OpenAI-совместимый API)
- openpyxl + reportlab

## Что НЕ работает (mock)

- ❌ Запись в 1С:ERP
- ❌ Реальный Watcher КОМПАС-3D
- ❌ Аутентификация
- ❌ RAG (Few-shot в промте хватит для прототипа)

## Контакты

- **Продукт:** Сергей Жуков, Первый БИТ
- **Клиент:** Баранов М.А. (гл. технолог Техинкома)

---

**Версия:** 0.1.0
