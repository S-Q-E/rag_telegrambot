# api/retriever.py
import os
from typing import List
from sqlalchemy.orm import Session, relationship
from sqlalchemy import text, Column, Integer, String, Text, DateTime, func, ForeignKey
from pgvector.sqlalchemy import Vector
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger
from openai import AsyncOpenAI
from datetime import datetime

from .db import Base

# --- Инициализация ---
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


class Document(Base):
    """Модель для хранения документов."""
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="uploaded")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Модель для хранения чанков документов в БД."""
    __tablename__ = 'document_chunks'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'))
    assistant_name = Column(String, index=True)
    content = Column(Text)
    # Размерность text-embedding-3-small равна 1536
    embedding = Column(Vector(1536))
    document = relationship("Document", back_populates="chunks")


async def get_openai_embedding(text_to_embed: str) -> List[float]:
    """Получает эмбеддинг для текста с помощью OpenAI API."""
    try:
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[text_to_embed]
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error getting embedding from OpenAI: {e}")
        raise


class Retriever:
    """
    Отвечает за загрузку, эмбеддинг и поиск документов.
    """
    def __init__(self, db_session: Session, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.db = db_session
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )

    async def add_document(self, assistant_name: str, file_name: str, content: str):
        """Разбивает на чанки и сохраняет один документ в БД."""
        logger.info(f"Processing uploaded document '{file_name}' for assistant '{assistant_name}'.")

        # Создаем новый документ
        document = Document(filename=file_name, status="processing")
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        chunks = self.text_splitter.split_text(content)
        logger.info(f"Split document '{file_name}' into {len(chunks)} chunks.")

        for chunk_content in chunks:
            # Добавляем источник в сам чанк для идентификации
            chunk_with_source = f"{chunk_content}\n\nSource: {file_name}"
            embedding = await get_openai_embedding(chunk_with_source)
            db_chunk = DocumentChunk(
                document_id=document.id,
                assistant_name=assistant_name,
                content=chunk_with_source,
                embedding=embedding
            )
            self.db.add(db_chunk)

        document.status = "ready"
        self.db.commit()
        logger.info(f"Successfully added and embedded document '{file_name}'.")

    async def load_and_embed_documents(self, assistant_name: str, docs_path: str):
        """Загружает, разбивает на чанки и сохраняет документы в БД, используя OpenAI для эмбеддингов."""
        logger.info(f"Processing documents for assistant '{assistant_name}' from '{docs_path}'...")

        count = self.db.query(DocumentChunk).filter_by(assistant_name=assistant_name).count()
        if count > 0:
            logger.info(f"Documents for '{assistant_name}' already exist. Skipping embedding.")
            return

        if not os.path.exists(docs_path) or not os.listdir(docs_path):
            logger.warning(f"Directory '{docs_path}' is empty or does not exist.")
            return

        loader = DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader)
        documents = loader.load()
        if not documents:
            logger.warning(f"No documents found in '{docs_path}'.")
            return

        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks.")

        for chunk in chunks:
            embedding = await get_openai_embedding(chunk.page_content)
            db_chunk = DocumentChunk(
                assistant_name=assistant_name,
                content=chunk.page_content,
                embedding=embedding
            )
            self.db.add(db_chunk)
        
        self.db.commit()
        logger.info(f"Successfully loaded and embedded documents for '{assistant_name}'.")

    async def search(self, query: str, assistant_name: str, top_k: int = 3) -> List[str]:
        """Ищет релевантные чанки в БД."""
        logger.info(f"Searching for relevant documents for query: '{query}'")
        
        query_embedding = await get_openai_embedding(query)

        results = self.db.query(DocumentChunk).filter(
            DocumentChunk.assistant_name == assistant_name
        ).order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()

        if not results:
            logger.warning("No relevant documents found.")
            return []

        logger.info(f"Found {len(results)} relevant chunks.")
        return [result.content for result in results]