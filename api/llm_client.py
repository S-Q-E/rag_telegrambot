# api/llm_client.py
from loguru import logger

class LLMClient:
    """
    Имитация клиента для большой языковой модели (LLM).
    В реальном проекте здесь будет интеграция с API (например, OpenAI, Anthropic, etc.).
    """
    def get_response(self, query: str, context: str) -> str:
        """
        Генерирует ответ на основе запроса и найденного контекста.
        """
        logger.info("Generating LLM response...")

        # Простой шаблон для имитации ответа
        prompt = f"""
        Используя следующий контекст, ответь на вопрос пользователя.
        Если контекст не содержит ответа, скажи, что не можешь помочь с этим вопросом.

        Контекст:
        ---
        {context}
        ---

        Вопрос: {query}
        """

        # Имитация ответа LLM
        mock_response = (
            f"Ответ на ваш вопрос '{query}':\n"
            f"На основе найденной информации: {context.strip()}"
        )
        
        logger.info(f"Generated prompt:\n{prompt}")
        logger.info(f"Mock LLM response: {mock_response}")
        
        return mock_response

