# api/llm_client.py
import os
from openai import AsyncOpenAI
from loguru import logger
from typing import Optional, Dict, Any

# Инициализируем асинхронный клиент OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class LLMClient:
    """
    Клиент для взаимодействия с OpenAI Chat Completion API.
    Возвращает структурированный ответ: {'response': str, 'sources': [str], 'confidence': float}
    """
    async def get_response(
        self,
        query: str,
        context: str,
        assistant_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info("Generating LLM response with OpenAI...")

        # Собираем системную подсказку из конфига ассистента (если есть) или дефолт
        persona = assistant_config.get("persona") if assistant_config else "assistant"
        tone = assistant_config.get("tone", "friendly") if assistant_config else "friendly"
        temperature = float(assistant_config.get("temperature", 0.8)) if assistant_config else 0.8
        system_prompt = assistant_config.get("system_prompt") if assistant_config else None

        if not system_prompt:
            # Дефолтное поведение: человечный тон, опираться только на контекст для фактов,
            # цитировать источники в квадратных скобках или в конце.
            system_prompt = f"""
Ты — {persona}, действуй в тоне: {tone}.
1) Отвечай вежливо и живо: используй короткие естественные фразы, при необходимости задавай уточняющие вопросы.
2) Для любых фактических утверждений используй ТОЛЬКО предоставленный контекст. Если факта нет в контексте — честно напиши: "К сожалению, в моем контексте нет информации по этому вопросу" и предложи уточнить запрос.
3) Если используешь информацию из контекста, обязательно укажи источники/файлы или отметки, откуда взята информация (например: [Источник: product_specs.txt]).
4) Формат ответа: основной текст — внятный и непринужденный. В конце добавь блок "Источники:" со списком использованных источников (если есть).
5) Оцени свою уверенность в ответе числом от 0 до 1 и верни его в поле confidence.
6) Не придумывай фактов. Если нужно предположить — пометь как предположение.
"""

        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Контекст:\n{context}\n\n---\n\nВопрос: {query}"}
                ],
                temperature=temperature,
                max_tokens=800,
            )

            answer_text = response.choices[0].message.content.strip()

            # Модель должна вернуть текст и в конце блок Источники: ... и Confidence: 0.87
            # Попробуем парсить эти данные простым способом (на случай, если модель вернула их).
            sources = []
            confidence = None
            # Простейший разбор: ищем строки "Источники:" и "Confidence:" / "Уверенность:"
            if "Источники:" in answer_text:
                parts = answer_text.rsplit("Источники:", 1)
                main = parts[0].strip()
                srcs = parts[1].strip()
                answer_text = main
                # разделим источники по строкам или запятым
                for line in srcs.splitlines():
                    line = line.strip()
                    if line:
                        sources.append(line)
            # Попробуем найти числовую уверенность
            for token in ["Confidence:", "Уверенность:", "Confidence", "Уверенность"]:
                if token in answer_text:
                    # если уверенность встроена в текст — извлечём простым поиском
                    pass

            # Если модель не отдала sources/confidence, оставим пустые/None
            logger.info("Successfully received response from OpenAI.")
            return {"response": answer_text, "sources": sources, "confidence": confidence}

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {"response": "Произошла ошибка при обращении к AI‑сервису. Пожалуйста, попробуйте позже.", "sources": [], "confidence": 0.0}