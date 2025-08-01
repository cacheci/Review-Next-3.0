import json
import time

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot import check_reviewer
from src.database.posts import get_post_db, PostModel
from src.database.users import get_users_db, ReviewerModel, BannedUserModel, SubmitterModel
from src.utils import notify_submitter


@check_reviewer
async def append_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args
    if len(arg) != 2:
        await update.message.reply_text("请提供投稿 ID 和备注内容。格式：/append <post_id> <comment>")
        return
    post_id, comment = arg
    post_id = int(post_id)
    comment = comment.strip()
    eff_user = update.effective_user
    if not comment:
        await update.message.reply_text("请提供要添加的备注内容。")
        return
    async with get_post_db() as session:
        async with session.begin():
            post_info = await session.execute(select(PostModel).filter_by(id=post_id))
            post_info = post_info.scalar_one_or_none()
            if not post_info:
                await update.message.reply_text(f"投稿 ID {post_id} 不存在。")
                return
            post_info.other = post_info.other or "{}"
            other_data = json.loads(post_info.other) or {}
            other_data.setdefault('comment', []).append({
                "comment": comment,
                "user_id": eff_user.id,
                "timestamp": int(time.time()),
            })
            post_info.other = json.dumps(other_data)
            await session.merge(post_info)
    await update.message.reply_text(
        f"已添加备注：{comment} 到投稿 ID {post_id}。\n")


@check_reviewer
async def remove_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args
    if len(arg) != 1:
        await update.message.reply_text("格式错误")
        return
    post_id = int(arg[0])
    async with get_post_db() as session:
        async with session.begin():
            post_info = await session.execute(select(PostModel).filter_by(id=post_id))
            post_info = post_info.scalar_one_or_none()
            if not post_info:
                await update.message.reply_text(f"投稿 ID {post_id} 不存在。")
                return
            post_info.other = post_info.other or "{}"
            other_data = json.loads(post_info.other) or {}
            comments = other_data.setdefault('comment', [])
            other_data['comment'] = [c for c in comments if c.get('user_id') != update.effective_user.id]
            post_info.other = json.dumps(other_data)
            await session.merge(post_info)
    await update.message.reply_text(f"已删除您的备注。")


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
    arg = context.args
    if len(arg) != 2:
        await update.message.reply_text("格式错误")
        return
    post_id, comment = context.args
    post_id = int(post_id)
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


@check_reviewer
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args
    if len(arg) != 2:
        await update.message.reply_text("请提供用户ID和封禁原因。")
        return
    user_id, reason = arg
    if not user_id.isdigit():
        await update.message.reply_text("用户ID必须是数字。")
        return
    user_id = int(user_id)
    reason = reason.strip()
    async with get_users_db() as session:
        async with session.begin():
            submitter = await session.execute(select(SubmitterModel).filter_by(user_id=user_id))
            submitter = submitter.scalar_one_or_none()
            ban_user = BannedUserModel(user_id=user_id, banned_reason=reason, banned_date=int(time.time()),
                                       banned_by=update.effective_user.id)
            if submitter:
                ban_user.username = submitter.username
                ban_user.fullname = submitter.fullname
            session.add(ban_user)
    await update.message.reply_text(f"已将用户 ID {user_id} 封禁，原因：{reason}.")


@check_reviewer
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args
    if len(arg) != 1:
        await update.message.reply_text("请提供用户ID和封禁原因。")
        return
    if not arg[0].isdigit():
        await update.message.reply_text("用户ID必须是数字。")
        return
    user_id = int(arg[0])
    async with get_users_db() as session:
        async with session.begin():
            banned_user = await session.execute(select(BannedUserModel).filter_by(user_id=user_id))
            banned_user = banned_user.scalar_one_or_none()
            if not banned_user:
                await update.message.reply_text(f"用户 ID {user_id} 未被封禁。")
                return
            await session.delete(banned_user)
    await update.message.reply_text(f"已解除用户 ID {user_id} 的封禁.")
