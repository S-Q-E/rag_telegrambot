# tests/test_bot.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, User

from bot.handlers_order import cmd_start, cq_assistant_select, handle_user_query, OrderState
from bot.services import get_rag_response

@pytest.fixture
async def dispatcher():
    """Фикстура для создания и настройки диспетчера."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return dp

@pytest.fixture
async def bot_mock():
    """Фикстура для мока бота."""
    return AsyncMock()

@pytest.mark.asyncio
async def test_cmd_start(bot_mock):
    """Тест для команды /start."""
    message = AsyncMock(spec=Message)
    message.from_user = User(id=123, is_bot=False, first_name="Test")
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=str(message.from_user.id))

    await cmd_start(message, state)

    message.answer.assert_called_once()
    assert "Здравствуйте! Я ваш AI-ассистент." in message.answer.call_args[0][0]
    current_state = await state.get_state()
    assert current_state == OrderState.waiting_for_assistant_choice

@pytest.mark.asyncio
async def test_cq_assistant_select(bot_mock):
    """Тест для выбора ассистента."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "assistant_dental"
    callback.from_user = User(id=123, is_bot=False, first_name="Test")
    callback.message = AsyncMock(spec=Message)
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=str(callback.from_user.id))
    await state.set_state(OrderState.waiting_for_assistant_choice)

    await cq_assistant_select(callback, state)

    callback.message.edit_text.assert_called_once()
    assert "Вы выбрали ассистента: <b>Dental</b>" in callback.message.edit_text.call_args[0][0]
    current_state = await state.get_state()
    assert current_state == OrderState.waiting_for_query
    user_data = await state.get_data()
    assert user_data["assistant"] == "dental"

@pytest.mark.asyncio
@patch("bot.handlers_order.get_rag_response", new_callable=AsyncMock)
async def test_handle_user_query(mock_get_rag_response):
    """Тест для обработки запроса пользователя."""
    mock_get_rag_response.return_value = "Вот ваш ответ."

    message = AsyncMock(spec=Message)
    message.text = "Сколько стоят виниры?"
    message.from_user = User(id=123, is_bot=False, first_name="Test")
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=str(message.from_user.id))
    await state.set_state(OrderState.waiting_for_query)
    await state.update_data(assistant="dental")

    await handle_user_query(message, state)

    message.answer.assert_any_call("⏳ Обрабатываю ваш запрос...")
    mock_get_rag_response.assert_called_once_with("dental", "Сколько стоят виниры?", "123")
    message.answer.assert_called_with("Вот ваш ответ.")

@pytest.mark.asyncio
async def test_get_rag_response_success():
    """Тест успешного ответа от RAG API."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Успешный ответ"}
        mock_post.return_value = mock_response

        response = await get_rag_response("test", "query", "123")
        assert response == "Успешный ответ"

@pytest.mark.asyncio
async def test_get_rag_response_http_error():
    """Тест ошибки HTTP при запросе к RAG API."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection error")):
        response = await get_rag_response("test", "query", "123")
        assert "Произошла непредвиденная ошибка" in response