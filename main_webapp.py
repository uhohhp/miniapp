import logging
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn

# Импортируем твои существующие модули
import database
import common_functions  # Здесь живет объект bot
import admin_functions  # Регистрируем хендлеры админки
import main as old_main_logic  # Импортируем логику старого main, если там есть хендлеры, кроме запуска
from schemas import Course, Topic, FileRequest, StatusResponse, FileMeta

# Настройка
WEBAPP_TOKEN = "secret_token_123"  # Замени на сложный ключ в продакшене
RATE_LIMIT_SECONDS = 2.0
last_requests = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Логика Бота в потоке ---
def run_bot():
    """Запускает polling бота в отдельном потоке"""
    logger.info("🤖 Запуск Telegram бота...")
    try:
        # Используем бота из common_functions, он уже настроен
        common_functions.bot.infinity_polling()
    except Exception as e:
        logger.error(f"Ошибка бота: {e}")


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Запускаем бота
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    yield
    # Shutdown: Бот (daemon) сам умрет при остановке процесса,
    # но по-хорошему тут можно вызвать bot.stop_polling()


app = FastAPI(lifespan=lifespan)

# CORS (чтобы фронт мог стучаться, если он на другом домене, но мы отдаем статику с того же)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API Endpoints ---

@app.get("/api/courses", response_model=List[Course])
def get_courses():
    """Возвращает список курсов"""
    raw_courses = database.get_all_courses()  # Возвращает [1, 2, 3]
    return [Course(id=c, title=f"Курс {c}") for c in raw_courses]


@app.get("/api/topics/{course_id}", response_model=List[Topic])
def get_topics(course_id: int):
    """Возвращает темы и доступные файлы"""
    topic_names = database.get_topics_by_course(course_id)
    if not topic_names:
        raise HTTPException(status_code=404, detail="Course not found or empty")

    result = []
    for t_name in topic_names:
        # Получаем детали лекции: (id, course, topic, audio, doc, pres, photo)
        lecture = database.get_lecture(course_id, t_name)
        if not lecture:
            continue

        # Маппинг файлов из БД в структуру API
        # Индексы из database.py: 3=audio, 4=doc, 5=pres, 6=photo
        files = []
        if lecture[3]: files.append(FileMeta(type="audio", file_id=lecture[3], name="Аудиозапись"))
        if lecture[4]: files.append(FileMeta(type="document", file_id=lecture[4], name="Документ"))
        if lecture[5]: files.append(FileMeta(type="presentation", file_id=lecture[5], name="Презентация"))
        if lecture[6]: files.append(FileMeta(type="photo", file_id=lecture[6], name="Фото"))

        result.append(Topic(course=course_id, title=t_name, files=files))

    return result


@app.post("/api/request_file", response_model=StatusResponse)
def request_file(req: FileRequest):
    """Отправляет файл пользователю в Telegram"""

    # 1. Проверка токена
    if req.webapp_token != WEBAPP_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid WebApp Token")

    # 2. Rate Limit
    now = time.time()
    last_time = last_requests.get(req.telegram_id, 0)
    if now - last_time < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="Слишком часто. Подождите пару секунд.")
    last_requests[req.telegram_id] = now

    # 3. Отправка через бота
    try:
        # common_functions.bot - это инстанс TeleBot
        # Telebot сам определит тип файла, но лучше использовать send_document для файлов
        # Мы просто пробуем отправить как документ, для фото/аудио телеграм обычно это кушает,
        # либо можно сделать switch по префиксу файла, если нужно.
        # Для простоты используем send_document, так как file_id универсален.

        # Небольшой хак: определяем метод по типу контента, если бы мы его передавали,
        # но send_document работает почти для всего, кроме voice.
        common_functions.bot.send_document(req.telegram_id, req.file_id, caption="📂 Ваш файл из Mini App")

        return StatusResponse(status="ok", message="Файл отправлен в чат")
    except Exception as e:
        logger.error(f"Failed to send file: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки файла: {str(e)}")


# Подключаем статику (Фронтенд)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main_webapp:app", host="0.0.0.0", port=8000, reload=True)