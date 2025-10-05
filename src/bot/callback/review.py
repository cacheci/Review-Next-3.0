import time

from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.bot import check_reviewer
from src.bot.callback import check_duplicate_cbq
from src.bot.command.admin import private_review
from src.config import ReviewConfig
from src.database.posts import get_post_db, PostLogModel, VoteType, PostModel, PostStatus
from src.utils import check_post_status


@check_reviewer
@check_duplicate_cbq
async def vote_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    eff_user = update.effective_user
    query_data = query.data.split("_")
    is_nsfw = False
    post_id = int(query_data[1])
    if len(query_data) == 3:
        is_nsfw = True
    vote_type = query_data[0]
    if vote_type.startswith("v3.0.private"):
        vote_type = vote_type.replace("v3.0.private#", "")
    is_change_vote = False
    # 获取稿件的信息
    async with get_post_db() as session:
        async with session.begin():
            result = await session.execute(select(PostModel).filter_by(id=post_id))
            post_data = result.scalar_one_or_none()
            if not post_data:
                await query.answer("❗️投稿不存在或已被处理，请稍后再试。")
                return -1
            if post_data.status != PostStatus.PENDING.value:
                await query.answer("❗️投稿已被处理，请稍后再试。")
                return -1
            result = await session.execute(select(PostLogModel).filter_by(post_id=post_id, reviewer_id=eff_user.id))
            existing_log = result.scalar_one_or_none()
            if existing_log:
                # await query.answer("❗️您已对此投稿投过票，请勿重复操作。")
                is_change_vote = True
            if vote_type == "v3.0.approve":
                vote_value = VoteType.APPROVE_NSFW.value if is_nsfw else VoteType.APPROVE.value
            elif vote_type == "v3.0.reject" or vote_type == "v3.0.rejectDuplicate":
                vote_value = VoteType.REJECT.value
            else:
                raise ValueError("Invalid vote type")
            if is_change_vote:
                if existing_log.vote == vote_value:
                    await query.answer("❗️您已对此投稿投过相同的投票，请勿重复操作。")
                    return 0
                existing_log.vote = vote_value
                existing_log.operate_time = int(time.time())
                await session.merge(existing_log)
            else:
                session.add(
                    PostLogModel(post_id=post_id, reviewer_id=eff_user.id, vote=vote_value, operate_type="reviewer",
                                 operate_time=int(time.time())))
            if vote_type == "v3.0.rejectDuplicate":
                session.add(PostLogModel(post_id=post_id, reviewer_id=eff_user.id, operate_type="system",
                                         operate_time=int(time.time()), msg="已在频道发布或已有人投稿"))
    rev_ret = await check_post_status(post_data, context)
    if is_change_vote:
        other_msg = "投票已更改"
    else:
        other_msg = "投票成功"
    if rev_ret == PostStatus.APPROVED.value:
        await query.answer(f"✅{other_msg}，此条投稿已通过")
        return PostStatus.APPROVED.value
    elif rev_ret == PostStatus.NEED_REASON.value:
        await query.answer(f"❎{other_msg}，此条投稿已被拒绝")
        return PostStatus.NEED_REASON.value
    elif rev_ret == PostStatus.REJECTED.value:
        await query.answer(f"❎{other_msg}，此条投稿已经拒绝处理完成")
        return PostStatus.REJECTED.value
    elif rev_ret == PostStatus.PENDING.value:
        await query.answer(f"✅{other_msg}~")
        return PostStatus.PENDING.value
    else:
        await query.answer("❗️投票失败，可能是因为此条投稿已被处理或不存在，请稍后再试。")
        return -1


@check_reviewer
@check_duplicate_cbq
async def choose_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    eff_user = update.effective_user
    reason = ReviewConfig.REJECTION_REASON
    query_data = query.data.split("_")
    if len(query_data) != 3:
        await query.answer("❗️无效的拒绝理由，请重新选择。")
        return
    post_id = int(query_data[1])
    reason_index = int(query_data[2])
    if reason_index < 0 or reason_index >= len(reason):
        await query.answer("❗️无效的拒绝理由，请重新选择。")
        return
    reason_msg = reason[reason_index]
    async with get_post_db() as session:
        async with session.begin():
            result = await session.execute(select(PostModel).filter_by(id=post_id))
            post_data = result.scalar_one_or_none()
            if not post_data:
                await query.answer("❗️投稿不存在或已被处理，请稍后再试。")
                return
            if post_data.status != PostStatus.NEED_REASON.value:
                await query.answer("❗️投稿状态不正确，请稍后再试。")
                return
            session.add(PostLogModel(post_id=post_id, reviewer_id=eff_user.id, operate_type="system",
                                     operate_time=int(time.time()), msg=reason_msg))
    rev_ret = await check_post_status(post_data, context)
    if rev_ret == 2:
        await query.answer("❎拒绝理由已选择，此条投稿已被拒绝。")
        return 1
    else:
        await query.answer("❌似乎存在错误，请联系开发者。")
        return 2


@check_reviewer
@check_duplicate_cbq
async def vote_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    eff_user = update.effective_user
    query_data = query.data.split("_")
    if len(query_data) != 2:
        await query.answer("❗️无效的撤回投票请求，请重新操作。")
        return
    post_id = int(query_data[1])
    async with get_post_db() as session:
        async with session.begin():
            result = await session.execute(
                select(PostLogModel).filter_by(post_id=int(post_id), reviewer_id=eff_user.id))
            logs = result.scalars().all()
            if not logs:
                await query.answer("❗️您没有对此投稿投票，无法撤回。")
                return
            for log in logs:
                await session.delete(log)
    await query.answer("✅撤回投票成功。")


@check_reviewer
@check_duplicate_cbq
async def vote_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    eff_user = update.effective_user
    query_data = query.data.split("_")
    if len(query_data) != 2:
        await query.answer("❗️无效的数据，请重新操作。")
        return
    post_id = int(query_data[1])
    async with get_post_db() as session:
        result = await session.execute(
            select(PostLogModel).filter_by(post_id=int(post_id), reviewer_id=eff_user.id).limit(1))
        logs = result.scalar_one_or_none()
        if not logs:
            await query.answer("❗️您没有对此投稿投票。")
            return
        vote_info = logs.vote
        if vote_info == VoteType.APPROVE.value:
            vote_type = "您的投票是以 SFW 通过"
        elif vote_info == VoteType.REJECT.value:
            vote_type = "您的投票是拒绝"
        elif vote_info == VoteType.APPROVE_NSFW.value:
            vote_type = "您的投票是以 NSFW 通过"
        await query.answer(f"✅{vote_type}。")


@check_reviewer
async def private_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eff_user = update.effective_user
    vote_ret = await vote_post(update, context)
    if "review_private_post_id" not in context.user_data:
        await eff_user.send_message("❗️请重新发送命令开始审核。")
        return 1
    post_id = context.user_data["review_private_post_id"]
    post_msg_id = context.user_data["review_private_post_msg_id"]
    oper_id = context.user_data["review_private_operate_id"]
    if vote_ret == -1:
        await eff_user.send_message("❗️投票失败，可能是因为此条投稿已被处理或不存在，请稍后再试。")
        return
    elif vote_ret == PostStatus.APPROVED.value or vote_ret == PostStatus.PENDING.value or vote_ret == PostStatus.REJECTED.value:  # 审核通过/未审核完成 需要投票
        await context.bot.delete_message(chat_id=eff_user.id,message_id=post_msg_id)
        await context.bot.delete_message(chat_id=eff_user.id, message_id=oper_id)
        await private_review(update, context)
        return
    elif vote_ret == PostStatus.NEED_REASON.value:
        keyboard = []
        reason = ReviewConfig.REJECTION_REASON
        for i in range(0, len(reason), 2):
            row = [InlineKeyboardButton(reason[i], callback_data=f"pri#reason_{post_id}_{i}")]
            if i + 1 < len(reason):
                row.append(InlineKeyboardButton(reason[i + 1], callback_data=f"pri#reason_{post_id}_{i + 1}"))
            keyboard.append(row)
        keyboard.append(
            [
                InlineKeyboardButton("自定义理由", switch_inline_query_current_chat=f"customReason_{post_id}# "),
                InlineKeyboardButton("忽略此投稿", callback_data= f"pri#reason_{post_id}_skip"),
                InlineKeyboardButton(
                    "💬 回复投稿人",
                    switch_inline_query_current_chat=f"reply_{post_id}# ",
                )
            ]
        )
        await context.bot.edit_message_reply_markup(
            chat_id=eff_user.id,
            message_id=oper_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


@check_reviewer
async def private_choose_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ret = await choose_reason(update, context)
    if ret != 1:
        await update.effective_user.send_message("❗️拒绝理由选择失败，请重新操作。")
        return
    post_msg_id = context.user_data["review_private_post_msg_id"]
    oper_id = context.user_data["review_private_operate_id"]
    await context.bot.delete_message(chat_id=update.effective_user.id, message_id=post_msg_id)
    await context.bot.delete_message(chat_id=update.effective_user.id, message_id=oper_id)
    await private_review(update, context)
    return
