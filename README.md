# Workshop workflow app (laser → bend → weld → QC)

Стек: **FastAPI + SQLite + Jinja2 + openpyxl**.

## Запуск на Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Открыть: http://127.0.0.1:8000

## Что реализовано

- Загрузка Excel (лист `ORDER`, колонки A-F).
- Ввод `project_root_path`, `standard_root_path`, `daily_kits`, `total_kits`.
- Индексация PDF рекурсивно в SQLite (project/standard) + кнопка переиндексации.
- Маппинг PDF по ключу из колонки B (basename без `.dxf`, регистронезависимо).
- Нормализация ключей: raw/norm/compact для устойчивого поиска.
- Экран Лазер: группировка по материалу+толщине, qty_day, путь проекта для DXF, статус.
- Очереди Гибка/Сварка/ОТК по переходам статусов.
- Страница проблем `PDF missing`.
