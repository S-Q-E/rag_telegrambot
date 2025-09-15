# api/main.py
import os
import sys
import yaml
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from sentence_transformers import SentenceTransformer

from .retriever import Base, Retriever
from .llm_client import LLMClient
from .rag_pipeline import process_query

# --- Конфигурация ---
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

# Загрузка модели для эмбеддингов (может занять время при первом запуске)
logger.info("Loading embedding model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2') # 384-мерные векторы
logger.info("Embedding model loaded.")

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
    user_id: int

class QueryResponse(BaseModel):
    response: str

# --- События FastAPI ---
@app.on_event("startup")
def on_startup():
    """Действия при старте API."""
    logger.info("API starting up...")
    with engine.connect() as connection:
        # Включаем расширение pgvector
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()
    
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
    
    # Загружаем и индексируем документы для всех ассистентов
    logger.info("Loading and embedding documents for all assistants...")
    db = SessionLocal()
    retriever = Retriever(db, embedding_model)
    try:
        for config_file in os.listdir(CONFIGS_PATH):
            if config_file.endswith(".yaml"):
                assistant_name = config_file.replace(".yaml", "")
                docs_path = os.path.join(DATA_PATH, assistant_name)
                retriever.load_and_embed_documents(assistant_name, docs_path)
    finally:
        db.close()
    logger.info("Initial document processing complete.")

# --- Эндпоинты API ---
@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest, db: Session = Depends(get_db)):
    """Основной эндпоинт для обработки запросов к RAG."""
    logger.info(f"Received query for assistant '{request.assistant}' from user '{request.user_id}'")
    
    # Проверка существования ассистента
    config_path = os.path.join(CONFIGS_PATH, f"{request.assistant}.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Assistant '{request.assistant}' not found.")

    try:
        response_text = process_query(
            query=request.query,
            assistant_name=request.assistant,
            db_session=db,
            embedding_model=embedding_model,
            llm_client=llm_client
        )
        return QueryResponse(response: response_text)
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing the query.")

@app.get("/health")
def health_check():
    return {"status": "ok"}
