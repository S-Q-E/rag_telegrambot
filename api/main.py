import os
import sys
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger
import time

from .db import Base, engine, get_db, User
from .retriever import Retriever
from .llm_client import LLMClient
from .rag_pipeline import process_query
from .routes.documents import router as documents_router
from . import auth, crud, schemas
import yaml

# --- Конфигурация ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError(
        "ОШИБКА: Переменная окружения OPENAI_API_KEY не установлена или пуста. "
        "Пожалуйста, убедитесь, что в корне проекта есть файл .env и в нем прописан ваш ключ: "
        "OPENAI_API_KEY=sk-..."
    )

CONFIGS_PATH = os.path.abspath("configs")
DATA_PATH = os.path.abspath("data")

# --- Логирование ---
logger.remove()
logger.add(sys.stderr, level="INFO")

# --- Инициализация ---
app = FastAPI(title="RAG API")
llm_client = LLMClient()

templates = Jinja2Templates(directory=os.path.abspath("templates"))
app.mount("/static", StaticFiles(directory=os.path.abspath("static")), name="static")

app.include_router(documents_router, prefix="/api")
app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"Handled request {request.method} {request.url.path} - {response.status_code} in {duration:.2f}s")
    return response

# --- Модели Pydantic ---
class QueryRequest(BaseModel):
    assistant: str
    query: str
    user_id: Optional[str] = None # ID пользователя, если запрос от бота

class QueryResponse(BaseModel):
    response: str

# --- События FastAPI ---
@app.on_event("startup")
async def on_startup():
    """Действия при старте API."""
    logger.info("API starting up...")
    # Проверка и создание расширения и таблиц
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()
    Base.metadata.create_all(bind=engine)

    # Создание сервисного аккаунта для бота, если он не существует
    db = next(get_db())
    try:
        BOT_USER_EMAIL = os.getenv("BOT_USER_EMAIL")
        BOT_USER_PASSWORD = os.getenv("BOT_USER_PASSWORD")
        if BOT_USER_EMAIL and BOT_USER_PASSWORD:
            bot_user = crud.get_user_by_email(db, email=BOT_USER_EMAIL)
            if not bot_user:
                logger.info(f"Bot service account '{BOT_USER_EMAIL}' not found. Creating...")
                user_in = schemas.UserCreate(email=BOT_USER_EMAIL, password=BOT_USER_PASSWORD)
                hashed_password = auth.get_password_hash(user_in.password)
                crud.create_user(db=db, user=user_in, hashed_password=hashed_password)
                logger.info("Bot service account created successfully.")
            else:
                logger.info("Bot service account already exists.")
        else:
            logger.warning("BOT_USER_EMAIL or BOT_USER_PASSWORD are not set. Bot service account cannot be created.")
    finally:
        db.close()

    # Асинхронная загрузка и индексация документов
    logger.info("Loading and embedding documents for all assistants...")
    db = next(get_db())
    try:
        tasks = []
        if not os.path.exists(CONFIGS_PATH):
            logger.warning(f"Configs path {CONFIGS_PATH} not found.")
            return
        for config_file in os.listdir(CONFIGS_PATH):
            if not config_file.endswith(".yaml"):
                continue

            assistant_name = config_file.replace(".yaml", "")
            config_path = os.path.join(CONFIGS_PATH, config_file)

            # Загружаем конфиг ассистента
            try:
                with open(config_path, "r", encoding="utf-8") as fh:
                    assistant_config = yaml.safe_load(fh) or {}
            except Exception as e:
                logger.error(f"Failed to load config {config_path}: {e}")
                continue

            # Получаем параметры для ретривера из конфига
            retr_conf = assistant_config.get("retriever", {})
            chunk_size = retr_conf.get("chunk_size", 1000)
            chunk_overlap = retr_conf.get("chunk_overlap", 200)

            logger.info(f"Assistant '{assistant_name}': chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")

            # Создаем ретривер с правильными параметрами
            retriever = Retriever(db, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            docs_path = os.path.join(DATA_PATH, assistant_name)
            task = retriever.load_and_embed_documents(assistant_name, docs_path)
            tasks.append(task)

        await asyncio.gather(*tasks)
    finally:
        db.close()
    logger.info("Initial document processing complete.")

# --- Эндпоинты API ---
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    """Основной эндпоинт для обработки запросов к RAG."""

    BOT_USER_EMAIL = os.getenv("BOT_USER_EMAIL")
    user_id_for_query = None

    # Если запрос пришел от сервисного аккаунта бота
    if current_user.email == BOT_USER_EMAIL:
        if not request.user_id:
            raise HTTPException(status_code=400, detail="user_id is required for bot requests")
        user_id_for_query = request.user_id
        logger.info(f"Received query for assistant '{request.assistant}' from bot for user '{user_id_for_query}'")
    # Если запрос от обычного пользователя
    else:
        user_id_for_query = str(current_user.id)
        logger.info(f"Received query for assistant '{request.assistant}' from user '{user_id_for_query}'")

    config_path = os.path.join(CONFIGS_PATH, f"{request.assistant}.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Assistant '{request.assistant}' not found.")

    try:
        response_text = await process_query(
            query=request.query,
            assistant_name=request.assistant,
            user_id=user_id_for_query,
            db_session=db,
            llm_client=llm_client
        )
        return QueryResponse(response=response_text)
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing the query.")

@app.get("/health")
def health_check():
    return {"status": "ok"}