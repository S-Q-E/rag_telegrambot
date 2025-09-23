# bot/handlers_order.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
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


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    logger.info(f"User {message.from_user.id} type help command")
    await message.answer("Используйте команду \start чтобы начать работу с ботом\n"
                         "Используйте команду \mode чтобы поменять режим бота")

@router.message(Command("mode"))
async def cmd_mode(message: types.Message):
    await message.answer("Выберите ассистента", reply_markup=get_assistants_keyboard())


@router.callback_query(F.data.startswith("assistant_"))
async def get_assistant(callback: types.CallbackQuery, state: FSMContext):
    assistant_id = callback.data.split("_")[1]

    # сохраняем ассистента
    await state.update_data(assistant=assistant_id)

    logger.info(f"User {callback.from_user.id} selected assistant: {assistant_id}")

    await callback.message.edit_text(
        f"Вы выбрали ассистента: <b>{assistant_id.capitalize()}</b>.\n"
        f"Теперь вы можете задать свой вопрос."
    )
    await state.set_state(OrderState.waiting_for_query)
    await callback.answer()


# --- Обработчики колбэков ---
@router.callback_query(OrderState.waiting_for_assistant_choice, F.data.startswith("assistant_"))
async def cq_assistant_select(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора ассистента."""
    assistant_id = callback.data.split("_")[1]

    # сохраняем ассистента
    await state.update_data(assistant=assistant_id)

    logger.info(f"User {callback.from_user.id} selected assistant: {assistant_id}")

    await callback.message.edit_text(
        f"Вы выбрали ассистента: <b>{assistant_id.capitalize()}</b>.\n"
        f"Теперь вы можете задать свой вопрос."
    )
    await state.set_state(OrderState.waiting_for_query)
    await callback.answer()


# --- Основная логика диалога ---
@router.message(OrderState.waiting_for_query)
async def handle_user_query(message: types.Message, state: FSMContext):
    """Обработчик сообщений пользователя."""
    user_data = await state.get_data()
    assistant = user_data.get("assistant")

    query = message.text
    user_id = message.from_user.id

    if not query:
        await message.answer("Пожалуйста, введите ваш вопрос.")
        return

    # Показываем, что бот "печатает"
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action='typing')
    except Exception as e:
        logger.warning(f"Failed to send chat action: {e}")

    logger.info(f"User {user_id} sent query to '{assistant}': '{query}'")

    # Получаем ответ от API
    api_response = await get_rag_response(
        assistant=assistant,
        query=query,
        user_id=str(user_id)
    )

    response_text = ""
    sources_text = ""

    if isinstance(api_response, dict):
        response_text = api_response.get("response", "")
        sources = api_response.get("sources", [])
        confidence = api_response.get("confidence")
        if sources:
            sources_text = "\n\nИсточники:\n" + "\n".join(sources)
        if confidence is not None:
            sources_text += f"\n\n(Уверенность: {confidence})"
    else:
        response_text = str(api_response)

    # Логируем
    logger.debug(f"Response for user {user_id}: {response_text}")

    # Отправляем пользователю
    await message.answer(response_text + sources_text)
