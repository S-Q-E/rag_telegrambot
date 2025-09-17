# api/rag_pipeline.py
from sqlalchemy.orm import Session
from .retriever import Retriever, Message
from .llm_client import LLMClient
from loguru import logger
import os
import yaml
from sqlalchemy import desc

CONFIGS_PATH = os.getenv("CONFIGS_PATH", "configs")
MAX_HISTORY_LENGTH = 10
SUMMARIZATION_THRESHOLD = 20

async def save_message(db_session: Session, user_id: str, assistant: str, role: str, content: str):
    """Сохраняет сообщение в базу данных."""
    logger.info(f"Saving message for user {user_id}, role {role}")
    message = Message(
        user_id=user_id,
        assistant=assistant,
        role=role,
        content=content
    )
    db_session.add(message)
    db_session.commit()

async def get_history(db_session: Session, user_id: str, assistant: str) -> list[dict]:
    """Извлекает историю диалога из БД."""
    logger.info(f"Fetching history for user {user_id}, assistant {assistant}")
    messages = db_session.query(Message).filter(
        Message.user_id == user_id,
        Message.assistant == assistant
    ).order_by(desc(Message.created_at)).limit(MAX_HISTORY_LENGTH).all()
    
    history = [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]
    logger.info(f"Fetched {len(history)} messages from history.")
    return history

# api/rag_pipeline.py
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .retriever import Retriever, Message
from .llm_client import LLMClient
from loguru import logger
import os, yaml

CONFIGS_PATH = os.getenv("CONFIGS_PATH", "configs")
MAX_HISTORY_LENGTH = 10
SUMMARIZATION_THRESHOLD = 20

async def get_history(db_session: Session, user_id: str, assistant: str) -> list[dict]:
    """История диалога: только допустимые роли для Chat API."""
    logger.info(f"Fetching history for user {user_id}, assistant {assistant}")
    messages = (
        db_session.query(Message)
        .filter(
            Message.user_id == user_id,
            Message.assistant == assistant,
            Message.role.in_(("user", "assistant", "system"))  # ВАЖНО: нет 'summary'
        )
        .order_by(desc(Message.created_at))
        .limit(MAX_HISTORY_LENGTH)
        .all()
    )
    history = [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]
    logger.info(f"Fetched {len(history)} messages from history.")
    return history

async def summarize_dialog(db_session: Session, user_id: str, assistant: str, llm_client: LLMClient):
    """Суммаризация диалога: храним как system-сообщение."""
    logger.info(f"Summarizing dialog for user {user_id}, assistant {assistant}")
    messages = (
        db_session.query(Message)
        .filter(
            Message.user_id == user_id,
            Message.assistant == assistant,
            Message.role != 'system'  # игнорим предыдущую summary, если была
        )
        .order_by(Message.created_at)
        .all()
    )

    if len(messages) < SUMMARIZATION_THRESHOLD:
        return

    full_dialog = "\n".join([f"{m.role}: {m.content}" for m in messages])
    summary_prompt = (
        "Пожалуйста, сделай краткое изложение (summary) этого диалога в одном абзаце. "
        "Пиши по делу, без воды.\nДиалог:\n" + full_dialog
    )

    summary_dict = await llm_client.get_response(query=summary_prompt, context="")
    summary_text = summary_dict.get('response', '').strip()

    if summary_text:
        # Удаляем старые сообщения и оставляем только system-summary
        db_session.query(Message).filter(
            Message.user_id == user_id,
            Message.assistant == assistant
        ).delete()

        summary_message = Message(
            user_id=user_id,
            assistant=assistant,
            role='system',  # ВАЖНО: вместо 'summary'
            content=f"[Краткая сводка беседы]\n{summary_text}"
        )
        db_session.add(summary_message)
        db_session.commit()
        logger.info("Dialog summarized and old messages replaced.")


async def process_query(
    query: str,
    assistant_name: str,
    user_id: str, # Добавили user_id
    db_session: Session,
    llm_client: LLMClient
) -> str:
    """
    Основной pipeline: поиск по базе + генерация ответа с учетом истории.
    """
    logger.info(f"Processing query for assistant '{assistant_name}': '{query}'")

    # 1. Сохраняем сообщение пользователя
    await save_message(db_session, user_id, assistant_name, 'user', query)

    # 2. Извлекаем историю
    history = await get_history(db_session, user_id, assistant_name)

    config_path = os.path.join(CONFIGS_PATH, f"{assistant_name}.yaml")
    assistant_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                assistant_config = yaml.safe_load(fh) or {}
        except Exception as e:
            logger.warning(f"Failed to load assistant config {config_path}: {e}")

    # параметры ретривера из конфига
    retr_conf = (assistant_config or {}).get("retriever", {}) or {}
    top_k = int(retr_conf.get("top_k", 3))
    chunk_size = int(retr_conf.get("chunk_size", 1000))
    chunk_overlap = int(retr_conf.get("chunk_overlap", 200))

    # 3. Поиск релевантных чанков (с учетом параметров)
    retriever = Retriever(db_session, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    context_chunks = await retriever.search(query, assistant_name, top_k=top_k)
    context = "\n---\n".join(context_chunks) if context_chunks else ""

    # 5. Генерация через LLM
    llm_result = await llm_client.get_response(
        query=query,
        context=context,
        assistant_config=assistant_config,
        history=history
    )
    
    response_text = llm_result.get("response") if isinstance(llm_result, dict) else str(llm_result)

    # 6. Сохраняем ответ ассистента
    if response_text:
        await save_message(db_session, user_id, assistant_name, 'assistant', response_text)

    # 7. Проверяем необходимость суммаризации (в фоне)
    # В реальном приложении это лучше делать в фоновом воркере
    await summarize_dialog(db_session, user_id, assistant_name, llm_client)

    logger.debug(f"LLM response: {response_text[:200]}...")

    return response_text