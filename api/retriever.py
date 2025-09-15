# api/retriever.py
import os
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import VECTOR
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger

# Определение базовой модели SQLAlchemy
Base = declarative_base()

class DocumentChunk(Base):
    """Модель для хранения чанков документов в БД."""
    __tablename__ = 'document_chunks'
    id = Column(Integer, primary_key=True)
    assistant_name = Column(String, index=True)
    content = Column(Text)
    embedding = Column(VECTOR(384)) # Размерность зависит от модели эмбеддингов

class Retriever:
    """
    Отвечает за загрузку, эмбеддинг и поиск документов.
    """
    def __init__(self, db_session: Session, embedding_model):
        self.db = db_session
        self.embedding_model = embedding_model
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )

    def load_and_embed_documents(self, assistant_name: str, docs_path: str):
        """Загружает, разбивает на чанки и сохраняет документы в БД."""
        logger.info(f"Processing documents for assistant '{assistant_name}' from '{docs_path}'...")

        # Проверяем, есть ли уже документы для этого ассистента
        count = self.db.query(DocumentChunk).filter_by(assistant_name=assistant_name).count()
        if count > 0:
            logger.info(f"Documents for '{assistant_name}' already exist. Skipping embedding.")
            return

        if not os.path.exists(docs_path) or not os.listdir(docs_path):
            logger.warning(f"Directory '{docs_path}' is empty or does not exist.")
            return

        # Загрузка документов
        loader = DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader)
        documents = loader.load()
        if not documents:
            logger.warning(f"No documents found in '{docs_path}'.")
            return

        # Разбивка на чанки
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks.")

        # Создание эмбеддингов и сохранение
        for chunk in chunks:
            embedding = self.embedding_model.encode(chunk.page_content)
            db_chunk = DocumentChunk(
                assistant_name=assistant_name,
                content=chunk.page_content,
                embedding=embedding
            )
            self.db.add(db_chunk)
        
        self.db.commit()
        logger.info(f"Successfully loaded and embedded documents for '{assistant_name}'.")

    def search(self, query: str, assistant_name: str, top_k: int = 3) -> List[str]:
        """Ищет релевантные чанки в БД."""
        logger.info(f"Searching for relevant documents for query: '{query}'")
        
        query_embedding = self.embedding_model.encode(query)

        # Поиск по косинусному расстоянию
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
