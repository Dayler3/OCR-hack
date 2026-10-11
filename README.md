# Цифровой секретарь онлайн-деканата

Автономный комплекс для первичной обработки обращений студентов: принимает скан/фото
документа (JPG, PNG, PDF) и текстовый вопрос, распознаёт текст (OCR), заполняет карточку
реквизитов (пропуски — `«не найдено»`), проверяет документ по «Положению о приёме
документов» и формирует один из трёх детерминированных ответов со ссылкой на пункт
регламента. **Без внешних облачных LLM-API** — всё работает локально на CPU.

Монорепозиторий:

- `backend/` — Python 3.10+, FastAPI, PaddleOCR, Natasha, BM25 + rubert-tiny2
- `frontend/` — React 19 + TypeScript + Vite + Tailwind CSS + shadcn/ui
- `scripts/` — загрузка датасета, генерация синтетики, предскачивание моделей

Подробный план и архитектура — в [PLAN.md](PLAN.md), требования — в
[tech-requirements.md](tech-requirements.md).

## Быстрый старт

### 1. Один раз — окружение (из корня репозитория)

```powershell
# venv создаётся в КОРНЕ (Python 3.10–3.12, для PaddleOCR; 3.13+ не подходит)
python -m venv .venv
pip install -r backend/requirements.txt       # ядро (API/тесты работают без ML)
pip install -r backend/requirements-ml.txt    # опционально: PaddleOCR, Natasha, rubert-tiny2
npm install                                    # фронтенд-зависимости (workspaces)
```

> В этом репозитории `.venv` уже создан на Python 3.11 — повторно его создавать не нужно.
> Активировать venv не обязательно: команды ниже используют его интерпретатор напрямую.

### 2. Запуск (из корня репозитория)

```powershell
npm run dev        # бэкенд :8000 + фронтенд :5173 одной командой
```

Открыть http://localhost:5173. Логи обоих серверов идут в один терминал с префиксами `[api]` / `[web]`, Ctrl+C останавливает оба.

Отдельные команды и утилиты (тоже из корня):

```powershell
npm run dev:backend     # только uvicorn
npm run dev:frontend    # только vite
npm run test            # pytest (backend/tests)
npm run batch           # batch_eval.py → backend/results.json
npm run samples         # сгенерировать синтетические сканы
npm run models          # предскачать модели PaddleOCR/Natasha/rubert-tiny2
npm run build           # production-сборка фронтенда
```

Без npm — вручную (PowerShell, из корня):

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000   # терминал 1
cd frontend; npm run dev                                                # терминал 2
```

Проверка API: `curl http://127.0.0.1:8000/api/health` и `curl http://127.0.0.1:8000/api/schemas`.

### 3. Данные и оценка

```powershell
npm run dataset                                 # выборка MWS-Vision-Bench (нужен datasets)
npm run samples                                 # синтетика 3 типов документов
npm run batch                                   # пакетный прогон → backend/results.json
```

## Режимы деградации

Сервис спроектирован так, чтобы запускаться даже без тяжёлых ML-зависимостей:

| Компонент | Без ML-зависимостей | С requirements-ml.txt |
|---|---|---|
| OCR | понятная ошибка / Tesseract, если установлен в системе | PaddleOCR (PP-OCRv4, `lang=ru`) |
| ФИО (NER) | regex из YAML-схемы | Natasha + regex |
| RAG | BM25 (rank-bm25) | BM25 + эмбеддинги rubert-tiny2 |

## API

- `GET /api/health` — статус движков
- `GET /api/schemas` — типы документов из `configs/document_schemas.yaml`
- `POST /api/analyze` — multipart: `file`, `question`, `doc_type?` (пусто = автоопределение)

Структура ответа и три ветки вердикта (`OK | MISSING_FIELDS | NO_INFO`) описаны в
[PLAN.md §5](PLAN.md#5-контракты-зафиксировать-до-кода).
