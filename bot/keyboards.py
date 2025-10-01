# bot/keyboards.py
import os
import yaml
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton,\
    ReplyKeyboardMarkup, KeyboardButton

CONFIGS_PATH = "/app/configs"


def get_assistants_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с выбором ассистента."""
    buttons = []
    for config_file in sorted(os.listdir(CONFIGS_PATH)):
        if config_file.endswith(".yaml"):
            assistant_id = config_file.replace(".yaml", "")
            with open(os.path.join(CONFIGS_PATH, config_file), 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                assistant_name = config.get("display_name", assistant_id.capitalize())

            buttons.append(
                [InlineKeyboardButton(text=assistant_name, callback_data=f"assistant_{assistant_id}")]
            )

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отмены действия."""
    buttons = [[InlineKeyboardButton(text="Отмена", callback_data="cancel_upload")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📂 Документы"),
                KeyboardButton(text="🤖 Задать вопрос"),
            ],
            [
                KeyboardButton(text="⬆️ Загрузить документ"),
                KeyboardButton(text="🗑 Удалить документ"),
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
