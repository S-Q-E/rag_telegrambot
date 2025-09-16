# api/llm_client.py
import os
from openai import AsyncOpenAI
from loguru import logger
from typing import Optional, Dict, Any, List

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
        assistant_config: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        logger.info("Generating LLM response with OpenAI...")

        # --- Настройки ассистента ---
        persona = assistant_config.get("persona") if assistant_config else "assistant"
        tone = assistant_config.get("tone", "friendly") if assistant_config else "friendly"
        temperature = float(assistant_config.get("temperature", 0.8)) if assistant_config else 0.8
        system_prompt = assistant_config.get("system_prompt") if assistant_config else None

        if not system_prompt:
            system_prompt = f"""
Ты — {persona}, действуй в тоне: {tone}.
1) Отвечай вежливо и живо: используй короткие естественные фразы, при необходимости задавай уточняющие вопросы.
2) Для любых фактических утверждений используй ТОЛЬКО предоставленный контекст. 
   Если факта нет в контексте — честно напиши: "К сожалению, в моем контексте нет информации по этому вопросу" 
   и предложи уточнить запрос.
3) Если используешь информацию из контекста, обязательно укажи источники/файлы или отметки, 
   откуда взята информация (например: [Источник: product_specs.txt]).
4) Формат ответа: основной текст — живой и непринужденный. 
   В конце добавь блок "Источники:" со списком использованных источников (если есть).
5) Оцени свою уверенность в ответе числом от 0 до 1 и верни его в поле confidence.
6) Не придумывай фактов. Если нужно предположить — пометь как предположение.
"""

        # --- Сборка сообщений ---
        messages = [{"role": "system", "content": system_prompt}]

        # Добавляем историю
        if history:
            for turn in history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        # Добавляем текущий запрос
        messages.append(
            {
                "role": "user",
                "content": f"Контекст:\n{context}\n\n---\n\nВопрос: {query}",
            }
        )

        logger.debug(f"LLM messages: {messages}")

        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=800,
            )

            answer_text = response.choices[0].message.content.strip()

            # --- Парсинг результата ---
            sources = []
            confidence = None

            if "Источники:" in answer_text:
                parts = answer_text.rsplit("Источники:", 1)
                main = parts[0].strip()
                srcs = parts[1].strip()
                answer_text = main
                for line in srcs.splitlines():
                    line = line.strip()
                    if line:
                        sources.append(line)

            # Попробуем найти уверенность (например: "Уверенность: 0.87")
            for token in ["Уверенность:", "Confidence:"]:
                if token in answer_text:
                    try:
                        conf_part = answer_text.split(token)[-1].strip()
                        confidence = float(conf_part.split()[0])
                        answer_text = answer_text.replace(f"{token} {conf_part}", "").strip()
                        break
                    except Exception:
                        pass

            logger.info("Successfully received response from OpenAI.")
            return {"response": answer_text, "sources": sources, "confidence": confidence}

        except Exception as e:
            logger.exception(f"Error calling OpenAI API: {e}")
            return {
                "response": "Произошла ошибка при обращении к AI-сервису. Пожалуйста, попробуйте позже.",
                "sources": [],
                "confidence": 0.0,
            }
