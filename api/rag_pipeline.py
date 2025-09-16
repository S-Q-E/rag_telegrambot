# api/rag_pipeline.py
from sqlalchemy.orm import Session
from .retriever import Retriever
from .llm_client import LLMClient
from loguru import logger
import os
import yaml

CONFIGS_PATH = os.getenv("CONFIGS_PATH", "configs")

async def process_query(
    query: str,
    assistant_name: str,
    db_session: Session,
    llm_client: LLMClient,
    history=None
) -> str:
    """
    Основной pipeline: поиск по базе + генерация ответа с учетом истории.
    """
    logger.info(f"Processing query for assistant '{assistant_name}': '{query}'")

    # 1. Поиск релевантных чанков
    retriever = Retriever(db_session)
    context_chunks = await retriever.search(query, assistant_name)

    if not context_chunks:
        return "К сожалению, я не нашел информации по вашему вопросу."

    context = "\n---\n".join(context_chunks)

    # 2. Загружаем конфиг ассистента
    config_path = os.path.join(CONFIGS_PATH, f"{assistant_name}.yaml")
    assistant_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                assistant_config = yaml.safe_load(fh) or {}
        except Exception as e:
            logger.warning(f"Failed to load assistant config {config_path}: {e}")

    # 3. Генерация через LLM
    llm_result = await llm_client.get_response(
        query=query,
        context=context,
        assistant_config=assistant_config,
        history=history or []
    )

    # 4. Извлекаем текст
    response_text = llm_result.get("response") if isinstance(llm_result, dict) else str(llm_result)

    logger.debug(f"LLM response: {response_text[:200]}...")  # логируем только начало

    return response_text
