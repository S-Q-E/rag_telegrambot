# tests/test_bot.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

# Добавляем путь к проекту
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.handlers import handle_user_query, UserState
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, User

@pytest.mark.asyncio
async def test_handle_user_query():
    """Тест обработчика запросов пользователя с моком API."""
    
    # --- Настройка моков ---
    # Мок для httpx.AsyncClient
    mock_api_response = {"response": "API mock response"}
    mock_post = AsyncMock()
    mock_post.return_value.__aenter__.return_value.json.return_value = mock_api_response
    mock_post.return_value.__aenter__.return_value.raise_for_status = lambda: None

    # Мок для FSM
    storage = MemoryStorage()
    state = FSMContext(storage, key={"chat_id": 123, "user_id": 123, "bot_id": 456})
    await state.set_state(UserState.assistant_selected)
    await state.update_data(assistant="shop")

    # Мок для сообщения Telegram
    message = AsyncMock(spec=Message)
    message.text = "test query"
    message.from_user = User(id=123, is_bot=False, first_name="Test")
    
    # --- Вызов хендлера ---
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        # Устанавливаем API_URL для теста
        with patch.dict(os.environ, {'API_URL': 'http://fake-api/query'}):
            from bot import handlers
            handlers.API_URL = 'http://fake-api/query'
            
            await handle_user_query(message, state)

    # --- Проверки ---
    # Проверяем, что бот отправил сообщение "Обрабатываю ваш запрос..."
    message.answer.call_args_list[0].args[0] == "⏳ Обрабатываю ваш запрос..."
    
    # Проверяем, что был вызван API с правильными параметрами
    mock_post.assert_called_once_with(
        'http://fake-api/query',
        json={'assistant': 'shop', 'query': 'test query', 'user_id': 123}
    )
    
    # Проверяем, что бот отправил финальный ответ от API
    message.answer.call_args_list[1].args[0] == mock_api_response["response"]
