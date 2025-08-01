from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.database.users import get_users_db, ReviewerModel


async def append_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    post_id, comment = message.text.split(" ", 1)[1].split("###", 1)
    post_id = int(post_id.strip())
    comment = comment.strip()
    # 还没写完
    if not comment:
        await message.reply_text("请提供要添加的备注内容。")
        return
    await update.message.reply_text(
        f"已添加备注：{comment} 到投稿 ID {post_id}。\n")


async def become_reviewer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eff_user = update.effective_user
    async with get_users_db() as session:
        async with session.begin():
            reviewer_info = await session.execute(
                select(ReviewerModel).filter_by(user_id=eff_user.id)
            )
            reviewer_info = reviewer_info.scalar_one_or_none()
            if not reviewer_info:
                reviewer_info = ReviewerModel(
                    user_id=eff_user.id,
                    username=eff_user.username,
                    fullname=eff_user.full_name,
                )
                session.add(reviewer_info)
                await update.message.reply_text("您已成为审核员。")
            else:
                await update.message.reply_text("您已经是审核员了，无需再次申请。")
