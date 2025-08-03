from asyncio import sleep

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    print(query)
    await query.edit_message_text(text="操作已取消")
    await sleep(1)
    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=query.message.message_id
    )
    await query.answer("操作已取消")
    # 清除用户数据
    context.user_data.clear()