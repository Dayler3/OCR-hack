"""FastAPI-приложение: CORS для Vite-фронтенда, /api из routes.py.

Прогрев моделей — ленивый (при первом /api/analyze), чтобы dev-сервер
стартовал мгновенно даже без ML-зависимостей."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Цифровой секретарь онлайн-деканата",
    description="OCR + извлечение реквизитов + проверка по Положению. Без внешних LLM-API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
