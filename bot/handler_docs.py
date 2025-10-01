# bot/handlers_docs.py
import asyncio
import tempfile
import os
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram import Bot

import services

router = Router(name="docs")
logger = logging.getLogger(__name__)


@router.message(Command("docs"))
async def cmd_list_docs(message: Message):
    docs = await asyncio.to_thread(services.get_documents)
    if not docs:
        await message.answer("📂 Документы не найдены.")
        return

    lines = []
    for d in docs:
        doc_id = d.get("id") or d.get("doc_id") or d.get("_id") or str(d.get("id", "unknown"))
        filename = d.get("filename") or d.get("name") or d.get("title") or "unknown"
        lines.append(f"📄 {doc_id}: {filename}")
    text = "\n".join(lines)
    # Telegram ограничение на длину сообщения — при длинном списке можно отправлять частями
    await message.answer(text[:3900])


@router.message(F.document)
async def handle_file(message: Message, bot: Bot):
    """
    Пользователь присылает файл — сохраняем временно, отправляем в API в фоне.
    """
    doc = message.document
    # безопасный временный файл
    suffix = os.path.splitext(doc.file_name or "")[1] or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tmp_path = tf.name

    # скачать файл
    file_obj = await bot.get_file(doc.file_id)
    await bot.download_file(file_obj.file_path, tmp_path)

    # загружаем в background thread (embedding может занимать время)
    await message.answer("⏳ Загружаю документ и создаю эмбеддинги... Это может занять время.")
    res = await asyncio.to_thread(services.upload_document, tmp_path, doc.file_name)

    # удаляем временный файл
    try:
        os.remove(tmp_path)
    except Exception:
        logger.exception("Не удалось удалить временный файл %s", tmp_path)

    if res:
        await message.answer(f"✅ Документ {doc.file_name} загружен.")
    else:
        await message.answer("❌ Ошибка при загрузке документа. Посмотри логи сервера.")


@router.message(Command("del"))
async def cmd_delete_doc(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Используй: /del <doc_id>")
        return
    doc_id = args[1]
    ok = await asyncio.to_thread(services.delete_document, doc_id)
    if ok:
        await message.answer(f"🗑 Документ {doc_id} удалён.")
    else:
        await message.answer("❌ Ошибка при удалении документа.")


@router.message(Command("doc"))
async def cmd_get_doc(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Используй: /doc <doc_id>")
        return
    doc_id = args[1]
    doc = await asyncio.to_thread(services.get_document, doc_id)
    if not doc:
        await message.answer("❌ Документ не найден.")
        return
    await message.answer(
        f"📄 {doc.get('filename','unknown')}\n"
        f"ID: {doc.get('id')}\n"
        f"Размер: {doc.get('size','?')} байт\n"
        f"Дополнительно: {doc.get('meta', '')}"
    )
