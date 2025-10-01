# api/retriever.py
import os
from typing import List
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger
from openai import AsyncOpenAI

from .db import Document, DocumentChunk

# --- Инициализация ---
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


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

    async def add_document(self, file_name: str, content: str, user_id: int = None):
        """Разбивает на чанки и сохраняет один документ в БД. Обеспечивает идемпотентность."""
        logger.info(f"Processing document '{file_name}'.")

        # Ищем существующий документ или создаем новый
        document = self.db.query(Document).filter_by(filename=file_name, user_id=user_id).first()
        if not document:
            document = Document(filename=file_name, user_id=user_id)
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)

        # Проверяем, есть ли уже чанки для этого документа
        existing_chunks_count = self.db.query(DocumentChunk).filter_by(
            document_id=document.id
        ).count()

        if existing_chunks_count > 0:
            logger.info(f"Chunks for document '{file_name}' already exist. Skipping.")
            if document.status != "ready":
                document.status = "ready"
                self.db.commit()
            return

        document.status = "processing"
        self.db.commit()

        chunks = self.text_splitter.split_text(content)
        logger.info(f"Split document '{file_name}' into {len(chunks)} chunks.")

        for chunk_content in chunks:
            chunk_with_source = f"{chunk_content}\n\nSource: {file_name}"
            embedding = await get_openai_embedding(chunk_with_source)
            db_chunk = DocumentChunk(
                document_id=document.id,
                content=chunk_with_source,
                embedding=embedding
            )
            self.db.add(db_chunk)

        document.status = "ready"
        self.db.commit()
        logger.info(f"Successfully added and embedded document '{file_name}'.")

    async def load_and_embed_documents(self, docs_path: str):
        """Загружает, разбивает на чанки и сохраняет документы в БД, используя OpenAI для эмбеддингов."""
        logger.info(f"Processing documents from '{docs_path}'...")

        if not os.path.exists(docs_path) or not os.listdir(docs_path):
            logger.warning(f"Directory '{docs_path}' is empty or does not exist.")
            return

        loader = DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader)
        documents = loader.load()
        if not documents:
            logger.warning(f"No documents found in '{docs_path}'.")
            return

        logger.info(f"Found {len(documents)} documents to process.")

        for doc in documents:
            file_name = os.path.basename(doc.metadata.get("source", "unknown.txt"))
            content = doc.page_content
            await self.add_document(file_name, content)

        logger.info(f"Finished processing documents from '{docs_path}'.")

    async def search(self, query: str, top_k: int = 3) -> List[str]:
        """Ищет релевантные чанки в БД."""
        logger.info(f"Searching for relevant documents for query: '{query}'")

        query_embedding = await get_openai_embedding(query)

        results = self.db.query(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()

        if not results:
            logger.warning("No relevant documents found.")
            return []

        logger.info(f"Found {len(results)} relevant chunks.")
        return [result.content for result in results]
