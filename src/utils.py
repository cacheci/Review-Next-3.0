from telegram import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, \
    InlineKeyboardButton, InlineKeyboardMarkup

from src.config import ReviewConfig

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
                    callback_data=f"approve_NSFW_{post_id}",
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
                    switch_inline_query_current_chat=f"removeAppend_{post_id}#",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💬 回复投稿人",
                    switch_inline_query_current_chat=f"comment_{post_id}# ",
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
                switch_inline_query_current_chat=f"reject_{post_id}# ",
            ),
            InlineKeyboardButton("忽略此投稿", callback_data="reason_skip"),
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
