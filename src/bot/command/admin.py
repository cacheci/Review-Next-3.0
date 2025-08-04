import json
import os
import subprocess
import sys
import time
from typing import Any

from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from src.bot import check_reviewer
from src.config import BotConfig
from src.database.posts import get_post_db, PostModel, PostStatus, PostLogModel
from src.database.users import get_users_db, ReviewerModel, BannedUserModel, SubmitterModel
from src.logger import bot_logger
from src.utils import notify_submitter, MEDIA_GROUP_TYPES, check_post_status


async def update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in BotConfig.ADMIN:
        await update.message.reply_text("您没有权限执行此操作。")
        return
    try:
        subprocess.run(['git', 'pull'], check=True)
        await update.message.reply_text("Git 同步完成，正在重启")
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except subprocess.CalledProcessError:
        await update.message.reply_text("更新失败，请检查日志")

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
async def reply_submitter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def custom_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args
    if len(arg) != 2:
        await update.message.reply_text("格式错误")
        return
    post_id, reason_msg = context.args
    post_id = int(post_id)
    eff_user = update.effective_user
    async with get_post_db() as session:
        async with session.begin():
            result = await session.execute(select(PostModel).filter_by(id=post_id))
            post_data = result.scalar_one_or_none()
            if not post_data:
                await update.effective_message.reply_text("❗️投稿不存在或已被处理，请稍后再试。")
                return
            if post_data.status != PostStatus.NEED_REASON.value:
                await update.effective_message.reply_text("❗️投稿状态不正确，请稍后再试。")
                return
            session.add(PostLogModel(post_id=post_id, reviewer_id=eff_user.id, operate_type="system",
                                     operate_time=int(time.time()), msg=reason_msg))
    rev_ret = await check_post_status(post_data, context)
    if rev_ret == 2:
        await update.effective_message.reply_text("❎拒绝理由已选择，此条投稿已被拒绝。")
    else:
        await update.effective_message.reply_text("❌似乎存在错误，请联系开发者。")


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


async def get_post_list(u_id: int, page: int = 0) -> bool | list[Any]:
    posts_list = []
    async with get_post_db() as session:
        posts = await session.execute(
            select(PostModel)
            .filter_by(status=PostStatus.PENDING.value)
            .offset(page * 100)
            .limit(100)
        )
        posts = posts.scalars().all()
        if not posts:
            return False
        for post in posts:
            result = await session.execute(
                select(PostLogModel).filter_by(post_id=post.id, reviewer_id=u_id))
            logs = result.scalars().all()
            if not logs:
                posts_list.append(post.id)
    return posts_list


@check_reviewer
async def private_review_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_logger.info("Starting private review process")
    context.user_data["review_posts"] = []
    context.user_data["review_page"] = 0
    while True:
        ret = await get_new_post(update, context)
        if ret == ConversationHandler.END:
            bot_logger.info("No more posts to review.")
            return ConversationHandler.END
        else:
            await private_review(update, context)
            return 1


async def get_new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 私聊审核
    eff_user = update.effective_user
    old_post = context.user_data["review_posts"]
    if old_post and len(old_post) > 0:
        return
    posts_list = []
    while not posts_list:
        posts_new_list = await get_post_list(eff_user.id, context.user_data["review_page"])
        if type(posts_new_list) == bool:
            await eff_user.send_message("没有待审核的稿件。")
            return ConversationHandler.END
        context.user_data["review_page"] += 1
        posts_list.extend(posts_new_list)
    context.user_data["review_posts"] = posts_list
    return 2


async def private_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts_list = context.user_data.get("review_posts", [])
    eff_user = update.effective_user
    if update.callback_query:
        await update.callback_query.answer("正在尝试获取新的稿件")
    if update.effective_message.message_id:
        try:
            await update.effective_message.delete()
        except Exception as e:
            bot_logger.error(f"Failed to delete message: {e}")
    if not posts_list:
        if await get_new_post(update, context) == ConversationHandler.END:
            return ConversationHandler.END
        posts_list = context.user_data.get("review_posts", [])
    cur_post_id = posts_list.pop(0)
    context.user_data["review_posts"] = posts_list
    async with get_post_db() as session:
        post_info = await session.execute(select(PostModel).filter_by(id=cur_post_id))
        post_info = post_info.scalar_one_or_none()
        if not post_info:
            await eff_user.send_message(f"稿件 ID {cur_post_id} 不存在。")
            return
        # 发送稿件信息
        cur_id = str(cur_post_id)
        reply_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅SFW通过", callback_data=f"private#approve_{cur_id}"),
             InlineKeyboardButton("❌拒绝", callback_data=f"private#reject_{cur_id}")],
            [InlineKeyboardButton("✅NSFW通过", callback_data=f"private#approve_NSFW_{cur_id}"),
             InlineKeyboardButton("❌重复投稿拒绝", callback_data=f"private#rejectDuplicate_{cur_id}")],
            [InlineKeyboardButton("➡️下一条", callback_data="next_post"),
             InlineKeyboardButton("取消操作", callback_data="cancel")]
        ])
        send_text = post_info.text
        async with get_users_db() as udb_session:
            submitter = await udb_session.execute(
                select(SubmitterModel).filter_by(user_id=post_info.submitter_id))
            submitter = submitter.scalar_one_or_none()
        # 审核评论处理
        media_list = json.loads(post_info.attachment)
        if media_list:
            media = []
            for media_item in media_list:
                media.append(MEDIA_GROUP_TYPES[media_item["media_type"]](media=media_item["media_id"]))
            msg = await context.bot.send_media_group(chat_id=eff_user.id, media=media, caption=send_text,
                                                     parse_mode="HTML")
            msg_id = msg[0].id
            msg = msg[0]
        else:
            msg = await context.bot.send_message(chat_id=eff_user.id, text=send_text, parse_mode="HTML")
            msg_id = msg.id
        send_msg = "\n\n <b>稿件ID：</b>" + str(post_info.id)
        send_msg += "\n <b>投稿者：</b> @" + submitter.username + f" {submitter.fullname}"
        op_msg = await msg.reply_text(text=send_msg, parse_mode="HTML", reply_markup=reply_kb, do_quote=True)
        context.user_data["review_private_post_id"] = cur_id
        context.user_data["review_private_post_msg_id"] = msg_id
        context.user_data["review_private_operate_id"] = op_msg.id
    return
