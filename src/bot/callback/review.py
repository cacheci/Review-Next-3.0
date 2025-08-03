import json
import time

from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.bot import check_reviewer
from src.bot.callback import check_duplicate_cbq
from src.bot.command.admin import private_review
from src.config import ReviewConfig
from src.database.posts import get_post_db, PostLogModel, VoteType, PostModel, PostStatus
from src.database.users import UserOperation, get_users_db, SubmitterModel
from src.logger import bot_logger
from src.utils import MEDIA_GROUP_TYPES, generate_reject_keyboard, notify_submitter


async def check_post_status(post_data: PostModel, context: ContextTypes.DEFAULT_TYPE) -> int:
    async with get_post_db() as session:
        async with session.begin():
            result = await session.execute(
                select(PostLogModel).filter_by(post_id=post_data.id).order_by(PostLogModel.operate_time.asc()))
            logs = result.scalars().all()
            if not logs:
                return -1
            last_log = logs[-1]
            last_reviewer_id = last_log.reviewer_id
            is_nsfw = False
            reason = last_log.msg if last_log.operate_type == "system" else None
            if reason:
                post_data.status = PostStatus.REJECTED.value
            else:
                approve_count, reject_count, nsfw_count = 0, 0, 0
                for log in logs:
                    vote_info = log.vote
                    if vote_info == VoteType.APPROVE.value:
                        approve_count += 1
                    elif vote_info == VoteType.REJECT.value:
                        reject_count += 1
                    elif vote_info == VoteType.APPROVE_NSFW.value:
                        nsfw_count += 1
                        is_nsfw = True
                total_approve = approve_count + nsfw_count
                if total_approve >= ReviewConfig.APPROVE_NUMBER_REQUIRED:
                    new_log = PostLogModel(post_id=post_data.id, reviewer_id=last_reviewer_id, operate_type="system",
                                           operate_time=int(time.time()), msg="通过")
                    session.add(new_log)
                    post_data.status = PostStatus.APPROVED.value
                    last_log = new_log
                    last_reviewer_id = last_log.reviewer_id
                elif reject_count >= ReviewConfig.REJECT_NUMBER_REQUIRED:
                    post_data.status = PostStatus.NEED_REASON.value
            await session.merge(post_data)
    # 生成消息以及tag
    vote_icons = {
        VoteType.APPROVE.value: "🟢",
        VoteType.REJECT.value: "🔴",
        VoteType.APPROVE_NSFW.value: "🔞"
    }
    vote_types = {
        VoteType.APPROVE.value: "以 SFW 通过",
        VoteType.REJECT.value: "拒绝",
        VoteType.APPROVE_NSFW.value: "以 NSFW 通过"
    }
    tag = [f"#USER_{post_data.submitter_id}", f"#SUBMITTER_{post_data.submitter_id}"]
    msg_parts = []
    for log in logs:
        if log.operate_type == "system":
            continue
        vote_info = log.vote
        tag.append(f"#USER_{log.reviewer_id}")
        tag.append(f"#REVIEWER_{log.reviewer_id}")
        reviewer_info = await UserOperation.get_reviewer(log.reviewer_id)
        icon = vote_icons.get(vote_info, "")
        vote_type = vote_types.get(vote_info, "")
        msg_parts.append(
            f"- {icon} 由 {reviewer_info.fullname} (@{reviewer_info.username} reviewer_id) {vote_type}")
    msg_info = "\n".join(msg_parts) + "\n"
    if post_data.status == PostStatus.REJECTED.value:
        msg_info += f"-❗️拒绝人：{last_reviewer_id}，理由：{reason}\n"

    # 处理编辑消息，用户/审核数据
    async with get_users_db() as session:
        async with session.begin():
            submitter = await session.execute(
                select(SubmitterModel).filter_by(user_id=post_data.submitter_id))
            submitter = submitter.scalar_one_or_none()
            submitter.approved_count += 1
        keyboard = None
        if post_data.status == PostStatus.APPROVED.value:
            msg = (f"✅ 已通过稿件。\n"
                   f"投稿人：{submitter.fullname} (@{submitter.username} {submitter.user_id})\n"
                   f"审稿人：\n{msg_info}\n")
            tag.append(f"#APPROVED")
            chat_id = ReviewConfig.PUBLISH_CHANNEL
        elif post_data.status == PostStatus.REJECTED.value:
            msg = (f"❌ 已拒绝稿件。\n"
                   f"投稿人：{submitter.fullname} (@{submitter.username} {submitter.user_id})\n"
                   f"审稿人：\n{msg_info}\n"
                   f"当前状态：已拒绝\n")
            chat_id = ReviewConfig.REJECTED_CHANNEL
        elif post_data.status == PostStatus.NEED_REASON.value:
            msg = (f"❌ 已拒绝稿件。\n"
                   f"投稿人：{submitter.fullname} (@{submitter.username} {submitter.user_id})\n"
                   f"审稿人：\n{msg_info}\n"
                   f"当前状态：待选择理由\n")
            chat_id = None
            keyboard = generate_reject_keyboard(str(post_data.id))
        elif post_data.status == PostStatus.PENDING.value:
            return PostStatus.PENDING.value  # 仍在审核中
        msg += " ".join(tag)
        await context.bot.edit_message_text(msg, ReviewConfig.REVIEWER_GROUP, post_data.operate_msg_id,
                                            parse_mode="HTML", reply_markup=keyboard)
        if not chat_id:
            return PostStatus.NEED_REASON.value  # 已拒绝但未选择理由
        send_text = post_data.text
        # 审核评论处理
        if post_data.other:
            other_data = json.loads(post_data.other)
            if "comment" in other_data:
                comment = "\n\n".join(
                    [f"<b>审核注:</b> {c['comment']}" for c in other_data["comment"]])
                send_text += f"\n{comment}"
        media_list = json.loads(post_data.attachment)
        if media_list:
            media = []
            for media_item in media_list:
                media.append(MEDIA_GROUP_TYPES[media_item["media_type"]](media=media_item["media_id"]))
            if is_nsfw:
                inline_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("跳到下一条", url=f"https://t.me/")]]
                )
                skip_msg = await context.bot.send_message(
                    chat_id=ReviewConfig.PUBLISH_CHANNEL,
                    text="⚠️ #NSFW 提前预警",
                    reply_markup=inline_keyboard,
                )
            msg = await context.bot.send_media_group(chat_id=chat_id, media=media, caption=send_text, parse_mode="HTML",
                                                     has_spoiler=is_nsfw)
            pub_msg_id = msg[0].id
            if is_nsfw:
                url_parts = msg[-1].link.rsplit("/", 1)
                next_url = url_parts[0] + "/" + str(int(url_parts[-1]) + 1)
                inline_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("跳到下一条", url=next_url)]]
                )
                await skip_msg.edit_text(
                    text="⚠️ #NSFW 提前预警", reply_markup=inline_keyboard
                )
        else:
            msg = await context.bot.send_message(
                chat_id=ReviewConfig.PUBLISH_CHANNEL,
                text=send_text,
                parse_mode="HTML"
            )
            pub_msg_id = msg.id
        async with get_post_db() as post_db_session:
            async with post_db_session.begin():
                post_data.publish_msg_id = pub_msg_id
                post_data.finish_at = int(time.time())
                await post_db_session.merge(post_data)
    if post_data.status == PostStatus.APPROVED.value:
        await notify_submitter(post_data, context, "您的投稿已通过审核！")
        return PostStatus.APPROVED.value
    else:
        if isinstance(reason, str) and reason != "":
            await notify_submitter(post_data, context, "您的投稿被拒绝。\n拒绝原因: <b>" + reason + "</b>")
        return PostStatus.REJECTED.value


@check_reviewer
@check_duplicate_cbq
async def vote_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    eff_user = update.effective_user
    query_data = query.data.split("_")
    is_nsfw = False
    post_id = 0
    if len(query_data) == 2:
        post_id = int(query_data[1])
    elif len(query_data) == 3:
        is_nsfw = True
        post_id = int(query_data[2])
    vote_type = query_data[0]
    if vote_type.startswith("private"):
        vote_type = vote_type.replace("private#", "")
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
            if vote_type == "approve":
                vote_value = VoteType.APPROVE_NSFW.value if is_nsfw else VoteType.APPROVE.value
            elif vote_type == "reject" or vote_type == "rejectDuplicate":
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
            if vote_type == "rejectDuplicate":
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
    if query_data[2] == "skip":
        reason_msg = ""
    else:
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
    if "review_private_id" not in context.user_data:
        await eff_user.send_message("❗️请重新发送命令开始审核。")
        return 1
    post_id = context.user_data["review_private_id"]
    if vote_ret == -1:
        await eff_user.send_message("❗️投票失败，可能是因为此条投稿已被处理或不存在，请稍后再试。")
        return
    elif vote_ret == PostStatus.APPROVED.value or vote_ret == PostStatus.PENDING.value or vote_ret == PostStatus.REJECTED.value:  # 审核通过/未审核完成 需要投票
        await update.effective_message.delete()
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
                InlineKeyboardButton("自定义理由", switch_inline_query_current_chat=f"private_reject_{post_id}# "),
                InlineKeyboardButton("忽略此投稿", callback_data="pri#reason_skip"),
                InlineKeyboardButton(
                    "💬 回复投稿人",
                    switch_inline_query_current_chat=f"private_reply_{post_id}# ",
                )
            ]
        )
        await update.effective_message.edit_text('请选择拒绝理由', parse_mode="HTML",
                                                 reply_markup=InlineKeyboardMarkup(keyboard))
        return


@check_reviewer
async def private_choose_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ret = await choose_reason(update, context)
    if ret != 1:
        await update.effective_user.send_message("❗️拒绝理由选择失败，请重新操作。")
        return
    await private_review(update, context)
    return
