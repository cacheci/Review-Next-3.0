import os

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, InlineQueryHandler, MessageHandler, filters, \
    ConversationHandler

from src.bot import message
from src.bot.callback.review import vote_post, choose_reason, vote_revoke, vote_query, private_vote
from src.bot.callback.submit import confirm_submission
from src.bot.callback.users import cancel
from src.bot.command.admin import append_comment, become_reviewer, remove_comment, comment_submitter, ban, unban, \
    private_review_start, get_new_post, private_review
from src.bot.inline import inline_query
from src.config import BotConfig, Config, ReviewConfig
from src.logger import bot_logger

if Config.PROXY and Config.PROXY != "":
    os.environ['https_proxy'] = Config.PROXY
    os.environ['http_proxy'] = Config.PROXY


def run_bot():
    application = (Application.builder()
                   .token(BotConfig.BOT_TOKEN)
                   .concurrent_updates(True)
                   .connect_timeout(60)
                   .get_updates_connect_timeout(60)
                   .get_updates_read_timeout(60)
                   .get_updates_write_timeout(60)
                   .read_timeout(60)
                   .write_timeout(60)
                   .base_url(BotConfig.BASE_URL)
                   .build())

    # 投稿-私聊
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, message.submit_msg))

    ## 按钮回调
    application.add_handler(CallbackQueryHandler(cancel, pattern="cancel"))
    # 确认投稿
    application.add_handler(CallbackQueryHandler(confirm_submission, pattern="^submitConfirm"))
    # 审核部分回调
    application.add_handler(CallbackQueryHandler(vote_post, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(vote_post, pattern="^reject_"))
    application.add_handler(CallbackQueryHandler(vote_post, pattern="^rejectDuplicate_"))
    application.add_handler(CallbackQueryHandler(vote_query, pattern="^voteQuery_"))
    application.add_handler(CallbackQueryHandler(vote_revoke, pattern="^voteRevoke_"))

    application.add_handler(CallbackQueryHandler(choose_reason, pattern="^reason_"))

    #私聊审核
    application.add_handler(CallbackQueryHandler(private_vote, pattern="^private#"))

    #命令回调
    application.add_handler(CommandHandler("append", append_comment, filters=filters.Chat(
        chat_id=ReviewConfig.REVIEWER_GROUP)))
    application.add_handler(CommandHandler("removeAppend", remove_comment, filters=filters.Chat(
        chat_id=ReviewConfig.REVIEWER_GROUP)))
    application.add_handler(CommandHandler("reviewer", become_reviewer, filters=filters.Chat(
        chat_id=ReviewConfig.REVIEWER_GROUP)))
    application.add_handler(CommandHandler("comment", comment_submitter, filters=filters.Chat(
        chat_id=ReviewConfig.REVIEWER_GROUP)))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("cancel", cancel))
    # application.add_handler(CommandHandler("review", private_review, filters=filters.ChatType.PRIVATE))
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("review", private_review_start, filters=filters.ChatType.PRIVATE)
        ],
        states={
            1: [CallbackQueryHandler(callback=get_new_post, pattern="next_review_")],
            2: [MessageHandler(filters=~filters.UpdateType.EDITED_MESSAGE, callback=private_review)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)

    # 内联查询
    application.add_handler(InlineQueryHandler(inline_query))

    bot_logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
