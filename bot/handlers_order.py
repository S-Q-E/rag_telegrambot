# bot/handlers_order.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from keyboards import get_assistants_keyboard
from services import get_rag_response

# --- Инициализация ---
router = Router()

# --- Состояния FSM ---
class OrderState(StatesGroup):
    waiting_for_assistant_choice = State()
    waiting_for_query = State()

# --- Обработчики команд ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    logger.info(f"User {message.from_user.id} started the bot.")
    await state.clear()
    await message.answer(
        "Здравствуйте! Я ваш AI-ассистент. Выберите, с кем вы хотите поговорить:",
        reply_markup=get_assistants_keyboard()
    )
    await state.set_state(OrderState.waiting_for_assistant_choice)

# --- Обработчики колбэков ---
@router.callback_query(OrderState.waiting_for_assistant_choice, F.data.startswith("assistant_"))
async def cq_assistant_select(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора ассистента."""
    assistant_id = callback.data.split("_")[1]
    await state.update_data(assistant=assistant_id)
    await state.set_state(OrderState.waiting_for_query)
    
    logger.info(f"User {callback.from_user.id} selected assistant: {assistant_id}")

    await callback.message.edit_text(
        f"Вы выбрали ассистента: <b>{assistant_id.capitalize()}</b>.\n"
        f"Теперь вы можете задать свой вопрос."
    )
    await callback.answer()

# --- Обработчики сообщений ---
@router.message(OrderState.waiting_for_query)
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

    response_text = await get_rag_response(assistant, query, str(user_id))
    
    await message.answer(response_text)

@router.message()
async def handle_no_state(message: types.Message):
    """Если пользователь пишет без выбора ассистента."""
    await message.answer(
        "Пожалуйста, сначала выберите ассистента, нажав /start.",
    )
