# api/rag_pipeline.py
from sqlalchemy.orm import Session
from .retriever import Retriever
from .llm_client import LLMClient
from loguru import logger

def process_query(
    query: str,
    assistant_name: str,
    db_session: Session,
    embedding_model,
    llm_client: LLMClient
) -> str:
    """
    Полный RAG-пайплайн: поиск -> генерация ответа.
    """
    logger.info(f"Processing query for assistant '{assistant_name}': '{query}'")
    
    # 1. Поиск релевантных документов
    retriever = Retriever(db_session, embedding_model)
    context_chunks = retriever.search(query, assistant_name)
    
    if not context_chunks:
        return "К сожалению, я не нашел информации по вашему вопросу."
        
    context = "\n---\n".join(context_chunks)
    
    # 2. Генерация ответа с помощью LLM
    response = llm_client.get_response(query, context)
    
    return response
