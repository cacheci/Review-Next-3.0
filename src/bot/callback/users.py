from asyncio import sleep

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.config import Config_submit


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.edit_message_text(text="操作已取消")
        origin_message = update.effective_message.reply_to_message
        if origin_message and Config_submit.SUBMIT_DELETE_WHEN_CANCEL:
            await context.bot.delete_message(
                chat_id=origin_message.chat.id,
                message_id=origin_message.message_id
            )
        await query.answer("操作已取消")
    await sleep(2)
    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    # 清除用户数据
    context.user_data.clear()
    return ConversationHandler.END