# api/main.py
import os
import sys
import asyncio
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from .retriever import Base, Retriever
from .llm_client import LLMClient
from .rag_pipeline import process_query
import yaml

# --- Конфигурация ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError(
        "ОШИБКА: Переменная окружения OPENAI_API_KEY не установлена или пуста. "
        "Пожалуйста, убедитесь, что в корне проекта есть файл .env и в нем прописан ваш ключ: "
        "OPENAI_API_KEY=sk-..."
    )

DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("POSTGRES_DB")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

CONFIGS_PATH = "/app/configs"
DATA_PATH = "/app/data"

# --- Логирование ---
logger.remove()
logger.add(sys.stderr, level="INFO")

# --- Инициализация ---
app = FastAPI(title="RAG API")
llm_client = LLMClient()

# --- База данных ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Зависимость FastAPI для получения сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Модели Pydantic ---
class QueryRequest(BaseModel):
    assistant: str
    query: str
    user_id: str # Изменили на str для консистентности

class DocumentUploadRequest(BaseModel):
    assistant: str
    file_name: str
    content: str
    user_id: str

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

    # Асинхронная загрузка и индексация документов
    logger.info("Loading and embedding documents for all assistants...")
    db = SessionLocal()
    try:
        tasks = []
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
@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest, db: Session = Depends(get_db)):
    """Основной эндпоинт для обработки запросов к RAG."""
    logger.info(f"Received query for assistant '{request.assistant}' from user '{request.user_id}'")
    
    config_path = os.path.join(CONFIGS_PATH, f"{request.assistant}.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Assistant '{request.assistant}' not found.")

    try:
        response_text = await process_query(
            query=request.query,
            assistant_name=request.assistant,
            user_id=str(request.user_id),
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

@app.post("/upload-document/")
async def handle_upload_document(request: DocumentUploadRequest, db: Session = Depends(get_db)):
    """Эндпоинт для загрузки и обработки документа."""
    logger.info(f"Received document '{request.file_name}' for assistant '{request.assistant}' from user '{request.user_id}'.")

    config_path = os.path.join(CONFIGS_PATH, f"{request.assistant}.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Assistant '{request.assistant}' not found.")

    try:
        # В реальном приложении параметры ретривера лучше брать из конфига ассистента
        retriever = Retriever(db)
        await retriever.add_document(
            assistant_name=request.assistant,
            file_name=request.file_name,
            content=request.content
        )
        return {"message": f"Document '{request.file_name}' uploaded and processed successfully."}
    except Exception as e:
        logger.exception(f"Error processing document upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing the document.")