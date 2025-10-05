import json
import time

from telegram import Update
from telegram.constants import MessageOriginType
from telegram.ext import ContextTypes
from telegram.helpers import effective_message_type

from src.bot import check_banned
from src.config import ReviewConfig
from src.database.posts import get_post_db, PostModel
from src.database.users import UserOperation
from src.utils import get_media_group, clear_media_group, MEDIA_GROUP_TYPES, generate_review_keyboard


# noinspection PyUnresolvedReferences
@check_banned
async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    origin_message = update.effective_message.reply_to_message

    text = origin_message.text_html_urled or origin_message.caption_html_urled or ""
    # add forward origin
    if origin_message.forward_origin is not None:
        forward_string = "\n\n<i>from</i> "
        match origin_message.forward_origin.type:
            case MessageOriginType.USER:
                forward_string += f"<a href='tg://user?id={origin_message.forward_origin.sender_user.id}'>{origin_message.forward_origin.sender_user.full_name}</a>"
            case MessageOriginType.CHAT:
                forward_string += f"<a href='{origin_message.forward_origin.sender_chat.link}'>{origin_message.forward_origin.sender_chat.title}</a>"
            case MessageOriginType.CHANNEL:
                forward_string += f"<a href='{origin_message.forward_origin.chat.link}/{origin_message.forward_origin.message_id}'>{origin_message.forward_origin.chat.title}</a>"
            case MessageOriginType.HIDDEN_USER:
                forward_string += origin_message.forward_origin.sender_user_name
        text += forward_string

    # add submitter sign string
    if query.data == "v3.0.submitConfirm_real_name":
        sign_string = f"<i>via</i> <a href='tg://user?id={user.id}'>{user.full_name}</a>"
        # if the last line is a forward message, put in the same line
        if text.split("\n")[-1].startswith("<i>from</i>"):
            text += " " + sign_string
        else:
            text += "\n\n" + sign_string
    # 处理媒体组
    media = []
    media_database = []
    if origin_message.media_group_id:
        media_dicts = get_media_group(origin_message.media_group_id)
        for m_d in media_dicts:
            media.append(
                MEDIA_GROUP_TYPES[m_d["media_type"]](
                    media=m_d["media_id"]
                )
            )
            media_database.append({
                "media_type": m_d["media_type"],
                "media_id": m_d["media_id"],
            })
    # 判断是不是只有一个媒体的
    elif origin_message.effective_attachment:
        media_type = effective_message_type(origin_message)
        media_id = origin_message.effective_attachment[
            -1].file_id if origin_message.photo else origin_message.effective_attachment.file_id
        media.append(MEDIA_GROUP_TYPES[media_type](media=media_id))
        media_database.append({
            "media_type": media_type,
            "media_id": media_id,
        })
    # 如果没有媒体，纯文本投稿
    if not media:
        msg = await context.bot.send_message(
            chat_id=ReviewConfig.REVIEWER_GROUP,
            text=text,
            parse_mode="HTML"
        )
        msg_id = msg.id
    else:
        msg = await context.bot.send_media_group(chat_id=ReviewConfig.REVIEWER_GROUP, media=media, caption=text,
                                                 parse_mode="HTML")
        msg_id = msg[0].id
        msg = msg[0]
    clear_media_group(origin_message.media_group_id)

    send_msg = f"❔ 待审稿件\n投稿人： {user.full_name} (@{user.username}, {user.id})\n\n#USER_{user.id} #SUBMITTER_{user.id} #PENDING"
    post_id = str(int(time.time())) + str(msg_id)
    keyboard = generate_review_keyboard(post_id)
    operate_msg = await msg.reply_text(
        text=send_msg,
        reply_markup=keyboard,
        parse_mode="HTML",
        do_quote=True,
    )
    # 插入数据库
    async with get_post_db() as session:
        async with session.begin():
            post_data = PostModel(id=int(post_id), submitter_id=user.id, text=text,
                                  attachment=json.dumps(media_database), submitter_msg_id=origin_message.id,
                                  review_msg_id=msg_id, operate_msg_id=operate_msg.id, created_at=int(time.time()))
            session.add(post_data)

    await UserOperation.submitter_add_count(user.id)
    await query.edit_message_text(text="投稿成功")
