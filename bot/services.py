# bot/services.py
import httpx
import os
from loguru import logger

API_URL = os.getenv("API_URL", "http://api:8000")

async def get_rag_response(assistant: str, query: str, user_id: str, history=None):
    """
    Отправка запроса в RAG API и возврат ответа.
    """
    url = f"{API_URL}/query"  # ✅ Исправлено с /rag на /query
    payload = {
        "assistant": assistant,
        "query": query,
        "user_id": user_id,
        "history": history or []
    }

    logger.info(f"Sending request to RAG API: {payload}")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"RAG API response: {data}")
            return data
    except httpx.HTTPStatusError as e:
        logger.error(
            f"RAG API returned error {e.response.status_code}: {e.response.text}"
        )
        return {"response": "Извините, возникла ошибка при обработке запроса."}
    except Exception as e:
        logger.exception(f"Failed to get response from RAG API: {e}")
        return {"response": "Сервис временно недоступен."}
