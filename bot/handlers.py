# bot/handlers.py
import os
import httpx
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from keyboards import get_assistants_keyboard

# --- Инициализация ---
router = Router()
API_URL = os.getenv("API_URL")

# --- Состояния FSM ---
class UserState(StatesGroup):
    assistant_selected = State()

# --- Обработчики команд ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await message.answer(
        "Здравствуйте! Я ваш AI-ассистент. Выберите, с кем вы хотите поговорить:",
        reply_markup=get_assistants_keyboard()
    )

# --- Обработчики колбэков ---
@router.callback_query(F.data.startswith("assistant_"))
async def cq_assistant_select(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора ассистента."""
    assistant_id = callback.data.split("_")[1]
    await state.update_data(assistant=assistant_id)
    await state.set_state(UserState.assistant_selected)
    
    await callback.message.edit_text(
        f"Вы выбрали ассистента: <b>{assistant_id.capitalize()}</b>.\n"
        f"Теперь вы можете задать свой вопрос."
    )
    await callback.answer()

# --- Обработчики сообщений ---
@router.message(UserState.assistant_selected)
async def handle_user_query(message: types.Message, state: FSMContext):
    """Обрабатывает запрос пользователя к выбранному ассистенту."""
    user_data = await state.get_data()
    assistant = user_data.get("assistant")
    query = message.text
    user_id = message.from_user.id

    if not query:
        await message.answer("Пожалуйста, введите ваш вопрос.")
        return

    await message.answer("⏳ Обрабатываю ваш запрос...")
    logger.info(f"User {user_id} sent query to '{assistant}': '{query}'")

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
            
            logger.info(f"Received response from API: {api_response}")
            await message.answer(api_response.get("response", "Не удалось получить ответ."))

    except httpx.RequestError as e:
        logger.error(f"HTTP request error to API: {e}")
        await message.answer("Произошла ошибка при подключении к сервису. Попробуйте позже.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await message.answer("Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")

@router.message()
async def handle_no_state(message: types.Message):
    """Если пользователь пишет без выбора ассистента."""
    await message.answer(
        "Пожалуйста, сначала выберите ассистента.",
        reply_markup=get_assistants_keyboard()
    )
