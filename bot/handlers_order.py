# bot/handlers_order.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from bot.keyboards import get_main_menu
from keyboards import get_assistants_keyboard, get_cancel_keyboard
from services import get_rag_response, upload_document_to_api

# --- Инициализация ---
router = Router()


# --- Состояния FSM ---
class OrderState(StatesGroup):
    waiting_for_assistant_choice = State()
    waiting_for_query = State()
    waiting_for_document = State()


# --- Обработчики команд ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    logger.info(f"User {message.from_user.id} started the bot.")
    await state.clear()
    await message.answer(
        "Здравствуйте! Я ваш AI-ассистент. Выберите, с кем вы хотите поговорить:",
        reply_markup=get_main_menu()
    )
    await state.set_state(OrderState.waiting_for_assistant_choice)

@router.message(Command("upload"))
async def cmd_upload(message: types.Message, state: FSMContext):
    """Обработчик команды /upload."""
    user_data = await state.get_data()
    assistant = user_data.get("assistant")
    if not assistant:
        await message.answer("Сначала выберите ассистента с помощью команды /start.")
        return

    logger.info(f"User {message.from_user.id} wants to upload a document for assistant '{assistant}'.")
    await message.answer(
        f"Пожалуйста, отправьте .txt файл для ассистента <b>{assistant.capitalize()}</b>.",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(OrderState.waiting_for_document)


@router.message(OrderState.waiting_for_document, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    """Обработчик получения документа."""
    if not message.document.file_name.endswith('.txt'):
        await message.answer("Пожалуйста, отправьте файл в формате .txt.")
        return

    user_data = await state.get_data()
    assistant = user_data.get("assistant")
    user_id = str(message.from_user.id)

    await message.bot.send_chat_action(chat_id=message.chat.id, action='typing')

    try:
        file = await message.bot.get_file(message.document.file_id)
        file_content_bytes = await message.bot.download_file(file.file_path)
        file_content = file_content_bytes.read().decode('utf-8')

        # Вызов нового сервиса
        success, api_message = await upload_document_to_api(
            assistant=assistant,
            file_name=message.document.file_name,
            content=file_content,
            user_id=user_id
        )

        if success:
            await message.answer(f"✅ Файл '{message.document.file_name}' успешно загружен и обработан.")
            logger.info(f"Document '{message.document.file_name}' uploaded successfully for user {user_id}.")
        else:
            await message.answer(f"❌ Не удалось загрузить файл. Ошибка: {api_message}")

    except Exception as e:
        logger.exception("Failed to handle document.")
        await message.answer("Произошла ошибка при обработке файла.")

    # Возвращаемся в состояние диалога
    await state.set_state(OrderState.waiting_for_query)


@router.callback_query(F.data == "cancel_upload")
async def cq_cancel_upload(callback: types.CallbackQuery, state: FSMContext):
    """Отмена загрузки файла."""
    await callback.message.edit_text("Загрузка отменена.")
    await state.set_state(OrderState.waiting_for_query)
    await callback.answer()


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
@router.message(OrderState.waiting_for_query, ~F.text.startswith('/'))
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


@router.message(F.text == "🤖 Задать вопрос")
async def menu_query(message: types.Message, state: FSMContext):
    await message.answer("Напишите ваш вопрос:")
    await state.set_state(OrderState.waiting_for_query)

@router.message(F.text == "⬆️ Загрузить документ")
async def menu_upload(message: types.Message, state: FSMContext):
    await cmd_upload(message, state)

@router.message(F.text == "🗑 Удалить документ")
async def menu_delete(message: types.Message):
    await message.answer("Введите команду в формате: /del <doc_id>")

@router.message(F.text == "ℹ️ Помощь")
async def menu_help(message: types.Message):
    await cmd_help(message)
