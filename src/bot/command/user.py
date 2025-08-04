from telegram import Update
from telegram.ext import ContextTypes


async def help_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rep_text = (f"欢迎使用投稿机器人，使用 <code>/help </code> 查看帮助\n"
                f"基础教程:\n"
                f"发送任意消息/文本，即可完成投稿。\n")
    await update.message.reply_text(rep_text, parse_mode="HTML")