import httpx
import os
from loguru import logger
import asyncio

API_URL = os.getenv("API_URL", "http://api:8000")

class AuthManager:
    """Handles authentication for the bot against the API."""
    def __init__(self):
        self._token = None
        self._email = os.getenv("BOT_USER_EMAIL")
        self._password = os.getenv("BOT_USER_PASSWORD")
        self._lock = asyncio.Lock()

    async def get_auth_header(self) -> dict:
        """
        Retrieves the auth header. If the token is missing, it fetches a new one.
        """
        async with self._lock:
            # In a real-world scenario, you'd also check for token expiration.
            # For this use case, we'll just get it once on startup.
            if not self._token:
                logger.info("No auth token found, logging in as bot service account...")
                if not self._email or not self._password:
                    logger.error("BOT_USER_EMAIL or BOT_USER_PASSWORD are not set. Cannot authenticate.")
                    return {}
                
                login_url = f"{API_URL}/auth/login"
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            login_url,
                            data={"username": self._email, "password": self._password}
                        )
                        response.raise_for_status()
                        self._token = response.json()["access_token"]
                        logger.info("Successfully logged in as bot and acquired token.")
                except Exception as e:
                    logger.exception(f"Failed to log in as bot: {e}")
                    return {}
            
            return {"Authorization": f"Bearer {self._token}"}

auth_manager = AuthManager()

async def get_rag_response(assistant: str, query: str, user_id: str):
    """
    Отправка запроса в RAG API и возврат ответа.
    """
    url = f"{API_URL}/query"
    payload = {
        "assistant": assistant,
        "query": query,
        "user_id": user_id,
    }

    logger.info(f"Sending request to RAG API for user {user_id}")
    auth_header = await auth_manager.get_auth_header()
    if not auth_header:
        return {"response": "Ошибка аутентификации бота. Проверьте конфигурацию сервисного аккаунта."}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=auth_header)
            response.raise_for_status()
            data = response.json()
            logger.info(f"RAG API response: {data}")
            return data
    except httpx.HTTPStatusError as e:
        logger.error(
            f"RAG API returned error {e.response.status_code}: {e.response.text}"
        )
        if e.response.status_code == 401:
            return {"response": "Проблема с аутентификацией бота. Возможно, токен истек или невалиден."}
        return {"response": "Извините, возникла ошибка при обработке запроса к API."}
    except Exception as e:
        logger.exception(f"Failed to get response from RAG API: {e}")
        return {"response": "Сервис API временно недоступен."}


async def upload_document_to_api(assistant: str, file_name: str, content: str, user_id: str):
    """Отправка документа в API для обработки и эмбеддинга."""
    url = f"{API_URL}/api/documents"
    
    auth_header = await auth_manager.get_auth_header()
    if not auth_header:
        return False, "Ошибка аутентификации бота."

    data = {"assistant": assistant}
    files = {"file": (file_name, content, "text/plain")}
    
    logger.info(f"Sending document '{file_name}' to API for assistant '{assistant}'.")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, data=data, files=files, headers=auth_header)
            response.raise_for_status()
            return True, response.json().get("filename", "Успешно")
    except httpx.HTTPStatusError as e:
        error_message = e.response.json().get("detail", e.response.text)
        logger.error(f"API error while uploading document: {error_message}")
        return False, error_message
    except Exception as e:
        logger.exception("Failed to upload document to API.")
        return False, "Внутренняя ошибка сервера."
