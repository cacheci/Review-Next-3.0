import json

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot import check_reviewer
from src.database.posts import get_post_db, PostModel
from src.database.users import get_users_db, ReviewerModel
from src.utils import notify_submitter


@check_reviewer
async def append_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    post_id, comment = message.text.split(" ", 1)[1].split("###", 1)
    post_id = int(post_id.strip())
    comment = comment.strip()
    eff_user = update.effective_user
    if not comment:
        await message.reply_text("请提供要添加的备注内容。")
        return
    async with get_post_db() as session:
        async with session.begin():
            post_info = await session.execute(select(PostModel).filter_by(id=post_id))
            post_info = post_info.scalar_one_or_none()
            if not post_info:
                await message.reply_text(f"投稿 ID {post_id} 不存在。")
                return
            post_info.other = post_info.other or "{}"
            other_data = json.loads(post_info.other) or {}
            other_data.setdefault('comment', []).append({
                "comment": comment,
                "user_id": eff_user.id,
                "timestamp": int(message.date.timestamp()),
            })
            post_info.other = json.dumps(other_data)
            await session.merge(post_info)
    await update.message.reply_text(
        f"已添加备注：{comment} 到投稿 ID {post_id}。\n")


@check_reviewer
async def remove_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    post_id = message.text.split(" ", 1)[1]
    post_id = int(post_id.strip())
    eff_user = update.effective_user
    async with get_post_db() as session:
        async with session.begin():
            post_info = await session.execute(select(PostModel).filter_by(id=post_id))
            post_info = post_info.scalar_one_or_none()
            if not post_info:
                await message.reply_text(f"投稿 ID {post_id} 不存在。")
                return
            post_info.other = post_info.other or "{}"
            other_data = json.loads(post_info.other) or {}
            comments = other_data.setdefault('comment', [])
            other_data['comment'] = [c for c in comments if c.get('user_id') != eff_user.id]
            post_info.other = json.dumps(other_data)
            await session.merge(post_info)
    await message.reply_text(f"已删除您的备注。")


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


@check_reviewer
async def comment_submitter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post_id, comment = update.message.text.split(" ", 1)[1].split("###", 1)
    post_id = int(post_id.strip())
    comment = comment.strip()
    if not comment:
        await update.message.reply_text("请提供要添加的评论内容。")
        return
    async with get_post_db() as session:
        post_info = await session.execute(select(PostModel).filter_by(id=post_id))
        post_info = post_info.scalar_one_or_none()
        if not post_info:
            await update.message.reply_text(f"投稿 ID {post_id} 不存在。")
            return
        await notify_submitter(post_info, context, comment)
    await update.message.reply_text("已向投稿者发送评论。")
