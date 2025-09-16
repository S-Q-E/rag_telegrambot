# api/rag_pipeline.py
from sqlalchemy.orm import Session
from .retriever import Retriever
from .llm_client import LLMClient
from loguru import logger
import os
import yaml

CONFIGS_PATH = os.getenv("CONFIGS_PATH", "configs")  # уже используется в main.py

async def process_query(
    query: str,
    assistant_name: str,
    db_session: Session,
    llm_client: LLMClient
) -> str:
    logger.info(f"Processing query for assistant '{assistant_name}': '{query}'")

    # 1. Поиск релевантных чанков
    retriever = Retriever(db_session)
    context_chunks = await retriever.search(query, assistant_name)

    if not context_chunks:
        return "К сожалению, я не нашел информации по вашему вопросу."

    context = "\n---\n".join(context_chunks)

    # 2. Загружаем конфиг ассистента (если есть)
    config_path = os.path.join(CONFIGS_PATH, f"{assistant_name}.yaml")
    assistant_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                assistant_config = yaml.safe_load(fh) or {}
        except Exception as e:
            logger.warning(f"Failed to load assistant config {config_path}: {e}")

    # 3. Генерация через LLM
    llm_result = await llm_client.get_response(query, context, assistant_config=assistant_config)

    # llm_result может быть структурой; вернём удобную строку (bot/svc обработают дальше)
    # Если LLMClient вернул sources/confidence — можно вложить их в строку или вернуть как JSON (API)
    response_text = llm_result.get("response") if isinstance(llm_result, dict) else str(llm_result)
    return response_text