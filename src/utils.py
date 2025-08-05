import json
import time

from sqlalchemy import select
from telegram import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, \
    InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import ReviewConfig
from src.database.posts import PostModel, PostStatus, get_post_db, PostLogModel, VoteType
from src.database.users import UserOperation, SubmitterModel, get_users_db

MEDIA_GROUPS = {}

MEDIA_GROUP_TYPES = {
    "audio": InputMediaAudio,
    "document": InputMediaDocument,
    "photo": InputMediaPhoto,
    "video": InputMediaVideo,
}


def get_media_group(media_group_id: str):
    return MEDIA_GROUPS.get(media_group_id, [])


def clear_media_group(media_group_id: str):
    MEDIA_GROUPS.pop(media_group_id, None)


def clear_all_media_groups():
    MEDIA_GROUPS.clear()


def generate_review_keyboard(post_id: str, ) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🟢 通过",
                    callback_data=f"approve_{post_id}",
                ),
                InlineKeyboardButton(
                    "🟡 以 NSFW 通过",
                    callback_data=f"approve_{post_id}_NSFW",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔴 拒绝",
                    callback_data=f"reject_{post_id}",
                ),
                InlineKeyboardButton(
                    "🔴 以重复投稿拒绝",
                    callback_data=f"rejectDuplicate_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❔ 查询我的投票",
                    callback_data=f"voteQuery_{post_id}",
                ),
                InlineKeyboardButton(
                    "↩️ 撤回我的投票",
                    callback_data=f"voteRevoke_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📝 添加备注",
                    switch_inline_query_current_chat=f"append_{post_id}# ",
                ),
                InlineKeyboardButton(
                    "⬅️ 删除备注",
                    switch_inline_query_current_chat=f"removeAppend_{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💬 回复投稿人",
                    switch_inline_query_current_chat=f"reply_{post_id}# ",
                ),
            ],
        ]
    )


def generate_reject_keyboard(post_id: str, ) -> InlineKeyboardMarkup:
    keyboard = []
    reason = ReviewConfig.REJECTION_REASON
    for i in range(0, len(reason), 2):
        row = [InlineKeyboardButton(reason[i], callback_data=f"reason_{post_id}_{i}")]
        if i + 1 < len(reason):
            row.append(InlineKeyboardButton(reason[i + 1], callback_data=f"reason_{post_id}_{i + 1}"))
        keyboard.append(row)
    keyboard.append(
        [
            InlineKeyboardButton(
                "自定义理由",
                switch_inline_query_current_chat=f"customReason_{post_id}# ",
            ),
            InlineKeyboardButton("忽略此投稿[待开发]", callback_data=f"reason_{post_id}_skip"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                "💬 回复投稿人",
                switch_inline_query_current_chat=f"reply_{post_id}# ",
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)


async def notify_submitter(post_data: PostModel, context: ContextTypes.DEFAULT_TYPE, msg: str) -> None:
    post_msg_id = post_data.publish_msg_id
    if post_data.status == PostStatus.APPROVED.value:
        message_text = msg
        chat_id = str(ReviewConfig.PUBLISH_CHANNEL)
        if chat_id.startswith("-100"):
            chat_id = chat_id[4:]
            url = f"https://t.me/c/{chat_id}/{post_msg_id}"
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("在频道中查看", url=url),
                  InlineKeyboardButton("查看评论区", url=f"{url}?thread={post_msg_id}" )]]
            )
        else:
            url = f"https://t.me/{chat_id}/{post_msg_id}"
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("在频道中查看", url=url),
                  InlineKeyboardButton("查看评论区", url=url + "?comment=1")]]
            )
    elif post_data.status == PostStatus.REJECTED.value:
        if not ReviewConfig.RETRACT_NOTIFY:
            return
        message_text = msg
        chat_id = str(ReviewConfig.REJECTED_CHANNEL)
        if chat_id.startswith("-100"):
            chat_id = chat_id[4:]
            url = f"https://t.me/c/{chat_id}/{post_msg_id}"
        else:
            url = f"https://t.me/{chat_id}/{post_msg_id}"
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("在拒稿频道中查看", url=url)]]
        )
    else:
        message_text = "来自审核的回复消息：\n\n" + msg
        keyboard = None
    await context.bot.send_message(
        chat_id=post_data.submitter_id,
        text=message_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        reply_to_message_id=post_data.submitter_msg_id
    )


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
                media_type = media_item["media_type"]
                if media_type in ["photo", "video"]:
                    media.append(MEDIA_GROUP_TYPES[media_type](
                        media=media_item["media_id"],
                        has_spoiler=is_nsfw
                    ))
                else:
                    media.append(MEDIA_GROUP_TYPES[media_type](
                        media=media_item["media_id"]
                    ))

            if is_nsfw:
                inline_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("跳到下一条", url=f"https://t.me/")]]
                )
                skip_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ #NSFW 提前预警",
                    reply_markup=inline_keyboard,
                )
            msg = await context.bot.send_media_group(chat_id=chat_id, media=media, caption=send_text, parse_mode="HTML")
            pub_msg_id = msg[0].id
            if is_nsfw:
                pub_chat_id = str(chat_id)
                if pub_chat_id.startswith("-100"):
                    pub_chat_id = pub_chat_id[4:]
                    url = f"https://t.me/c/{pub_chat_id}/{pub_msg_id}"
                else:
                    url = f"https://t.me/{pub_chat_id}/{pub_msg_id}"
                inline_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("跳到下一条", url=url)]]
                )
                await skip_msg.edit_text(
                    text="⚠️ #NSFW 提前预警", reply_markup=inline_keyboard
                )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
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
