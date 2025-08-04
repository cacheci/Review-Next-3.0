from uuid import uuid4

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

from src.bot import check_banned


@check_banned
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    if not query or query == "help":
        results = [InlineQueryResultArticle(
            id=str(uuid4()),
            title="inline模式仅限于审核用于处理稿件信息哦~",
            input_message_content=InputTextMessageContent("输入help获取帮助")
        )
        ]
        await update.inline_query.answer(results)
        return None

    if query.startswith("append_"):
        # 添加备注
        data = query.split("#", 1)
        id_data = data[0].replace("append_", "")
        id_data = int(id_data.strip())
        reply_text = data[1].strip() if len(data) > 1 else None
        if not reply_text:
            await update.inline_query.answer(
                [InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="请在输入框内输入要添加的备注内容",
                    input_message_content=InputTextMessageContent("请输入要添加的备注内容")
                )]
            )
            return None
        await update.inline_query.answer(
            [InlineQueryResultArticle(
                id=str(uuid4()),
                title=f"点此确认添加备注：{reply_text}",
                input_message_content=InputTextMessageContent(f"/append {id_data} {reply_text}")
            )]
        )
    elif query.startswith("removeAppend_"):
        # 删除备注
        id_data = query.replace("removeAppend_", "")
        id_data = int(id_data.strip())
        await update.inline_query.answer(
            [InlineQueryResultArticle(
                id=str(uuid4()),
                title=f"点此确认移除你添加的备注",
                input_message_content=InputTextMessageContent(f"/removeAppend {id_data}")
            )]
        )
    elif query.startswith("reply_"):
        # 删除备注
        data = query.split("#", 1)
        id_data = data[0].replace("reply_", "")
        id_data = int(id_data.strip())
        reply_text = data[1].strip() if len(data) > 1 else None
        if not reply_text:
            await update.inline_query.answer(
                [InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="请在输入框内输入回复内容",
                    input_message_content=InputTextMessageContent("请在输入框内输入回复内容")
                )]
            )
            return None
        await update.inline_query.answer(
            [InlineQueryResultArticle(
                id=str(uuid4()),
                title=f"点此回复内容：{reply_text}",
                input_message_content=InputTextMessageContent(f"/reply {id_data} {reply_text}")
            )]
        )