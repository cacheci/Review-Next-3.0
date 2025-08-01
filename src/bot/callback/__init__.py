from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes


def check_duplicate_cbq(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        query = update.callback_query
        unique_data = query.data + (
            query.inline_message_id
            if query.inline_message_id
            else str(query.message.message_id)
        )
        if ("cbq" not in context.user_data or
                context.user_data["cbq"] != unique_data):
            context.user_data["cbq"] = unique_data
        else:
            await query.answer("❗️请勿重复操作", show_alert=True)
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
