from asyncio import sleep

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.edit_message_text(text="操作已取消")
        await query.answer("操作已取消")
    else:
        await update.message.delete()
    msg = await update.effective_user.send_message("操作取消.", reply_markup=ReplyKeyboardRemove())
    await sleep(1)
    await msg.delete()
    # 清除用户数据
    context.user_data.clear()