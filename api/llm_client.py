# api/llm_client.py
import os
from openai import AsyncOpenAI
from loguru import logger

# Инициализируем асинхронный клиент OpenAI
# API-ключ будет взят из переменной окружения OPENAI_API_KEY
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class LLMClient:
    """
    Клиент для взаимодействия с OpenAI Chat Completion API.
    """
    async def get_response(self, query: str, context: str) -> str:
        """
        Генерирует ответ на основе запроса и найденного контекста с помощью OpenAI.
        """
        logger.info("Generating LLM response with OpenAI...")

        system_prompt = """
        Ты — полезный ассистент. Используя предоставленный контекст, ответь на вопрос пользователя.
        Отвечай только на основе контекста. Если в контексте нет ответа, скажи: 'К сожалению, я не нашел информации по вашему вопросу.'
        """

        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Контекст:\n{context}\n\n---\n\nВопрос: {query}"}
                ],
                temperature=0.7,
            )
            
            answer = response.choices[0].message.content
            logger.info("Successfully received response from OpenAI.")
            return answer.strip()

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Произошла ошибка при обращении к AI-сервису. Пожалуйста, попробуйте позже."