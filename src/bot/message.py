import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.helpers import effective_message_type
from src.bot import check_banned

MEDIA_GROUP_STATE = {}

from src.utils import MEDIA_GROUPS


async def send_submit_confirmation(message):
    await message.reply_text(
        """❔确认投稿？（确认前可以编辑内容，确认后无法编辑）

请确认稿件不包含以下内容，否则可能不会被通过：
 \\- AI生成的 *低质* 内容
 \\- 过于哗众取宠、摆拍卖蠢（傻逼不算沙雕）
 \\- 火星救援
 \\- 恶俗性挂人
 \\- 纯链接（出于安全考虑，本频道不允许链接预览，请见谅）

具体投稿规则详见[此处](https://t.me/woshadiao/181148)，随时可供查阅。

稿件将由多位管理投票审核，每位管理的审核标准可能不一，投票制可以改善这类问题，但仍可能对部分圈内的梗不太熟悉，请您理解。""",
        parse_mode='MarkdownV2',
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("署名投稿", callback_data="submitConfirm_real_name"),
                    InlineKeyboardButton("匿名投稿", callback_data="submitConfirm"),
                ],
                [InlineKeyboardButton("取消投稿", callback_data="cancel")],
            ]
        ),
        do_quote=True,
    )


async def process_media_group(message):
    """处理媒体组消息"""
    group_id = str(message.media_group_id)
    current_time = time.time()
    msg_dict = {
        "media_type": effective_message_type(message),
        "media_id": message.photo[-1].file_id
        if message.photo
        else message.effective_attachment.file_id,
        "post_id": message.message_id,
    }
    MEDIA_GROUPS.setdefault(group_id, []).append(msg_dict)
    if group_id not in MEDIA_GROUP_STATE:
        MEDIA_GROUP_STATE[group_id] = {"timestamp": current_time, "message": message, "pending": True}
        asyncio.create_task(check_and_send_confirmation(group_id))
    else:
        MEDIA_GROUP_STATE[group_id]["timestamp"] = current_time
        MEDIA_GROUP_STATE[group_id]["message"] = message


async def check_and_send_confirmation(group_id: str):
    while group_id in MEDIA_GROUP_STATE and MEDIA_GROUP_STATE[group_id]["pending"]:
        await asyncio.sleep(1)
        if group_id not in MEDIA_GROUP_STATE or not MEDIA_GROUP_STATE[group_id]["pending"]:
            break

        current_time = time.time()
        last_update_time = MEDIA_GROUP_STATE[group_id]["timestamp"]

        if current_time - last_update_time >= 1.0:
            message = MEDIA_GROUP_STATE[group_id]["message"]
            MEDIA_GROUP_STATE[group_id]["pending"] = False
            if message:
                await send_submit_confirmation(message)
            MEDIA_GROUP_STATE.pop(group_id, None)
            break


# 投稿处理
@check_banned
async def submit_msg(update: Update, context: CallbackContext):
    if update.business_message or not update.message:
        return
    message = update.effective_message
    if message.media_group_id:
        await process_media_group(message)
    else:
        await send_submit_confirmation(message)
