from telegram import Update
from telegram.ext import ContextTypes


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(text="操作已取消")
    await query.answer("操作已取消")