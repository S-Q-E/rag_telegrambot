# bot/keyboards.py
import os
import yaml
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
