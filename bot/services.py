# bot/services.py
import os
import httpx
from loguru import logger
from typing import Union, Dict, Any

API_URL = os.getenv("API_URL")

async def get_rag_response(assistant: str, query: str, user_id: str) -> Union[str, Dict[str, Any]]:
    logger.info(f"Sending request to RAG API for user {user_id} with assistant '{assistant}'")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                API_URL,
                json={
                    "assistant": assistant,
                    "query": query,
                    "user_id": user_id
                }
            )
            response.raise_for_status()
            api_response = response.json()
            logger.info(f"Received response from RAG API: {api_response}")

            # Поддержка двух форматов: {"response": "text"} или {"response": "...", "sources": [...], "confidence": ...}
            if isinstance(api_response, dict) and ("response" in api_response):
                return api_response
            # Для совместимости: если API вернул plain text
            if isinstance(api_response, str):
                return api_response
            return {"response": "Не удалось получить ответ."}
    except httpx.RequestError as e:
        logger.error(f"HTTP request error to RAG API: {e}")
        return "Произошла ошибка при подключении к сервису. Попробуйте позже."
    except Exception as e:
        logger.error(f"An unexpected error occurred in RAG API call: {e}")
        return "Произошла непредвиденная ошибка. Попробуйте позже."