import os

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, InlineQueryHandler, MessageHandler, filters, \
    ConversationHandler

from src.bot import message
from src.bot.callback.inline import inline_query
from src.bot.callback.review import vote_post, choose_reason, vote_revoke, vote_query, private_vote, \
    private_choose_reason
from src.bot.callback.submit import confirm_submission
from src.bot.callback.users import cancel
from src.bot.command.admin import append_comment, become_reviewer, remove_comment, reply_submitter, ban, unban, \
    private_review_start, private_review, custom_reason, update
from src.bot.command.user import help_info
from src.config import BotConfig, Config, ReviewConfig
from src.logger import bot_logger

if Config.PROXY and Config.PROXY != "":
    os.environ['https_proxy'] = Config.PROXY
    os.environ['http_proxy'] = Config.PROXY


def run_bot():
    application = (Application.builder()
                   .token(BotConfig.BOT_TOKEN)
                   .concurrent_updates(True)
                   .connect_timeout(BotConfig.TIMEOUT)
                   .get_updates_connect_timeout(BotConfig.TIMEOUT)
                   .get_updates_read_timeout(BotConfig.TIMEOUT)
                   .get_updates_write_timeout(BotConfig.TIMEOUT)
                   .read_timeout(BotConfig.TIMEOUT)
                   .write_timeout(BotConfig.TIMEOUT)
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

    # 选择拒绝原因
    application.add_handler(CallbackQueryHandler(choose_reason, pattern="^reason_"))

    # 私聊审核
    application.add_handler(CallbackQueryHandler(private_vote, pattern="^private#"))
    application.add_handler(CallbackQueryHandler(private_choose_reason, pattern="^pri#reason_"))

    # 命令回调
    application.add_handler(CommandHandler("help", help_info))
    application.add_handler(CommandHandler("start", help_info))
    application.add_handler(CommandHandler("append", append_comment))
    application.add_handler(CommandHandler("removeAppend", remove_comment))
    application.add_handler(CommandHandler("reviewer", become_reviewer, filters=filters.Chat(
        chat_id=ReviewConfig.REVIEWER_GROUP)))
    application.add_handler(CommandHandler("reply", reply_submitter))
    application.add_handler(CommandHandler("customReason", custom_reason))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))

    application.add_handler(CommandHandler("update", update))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("review", private_review_start, filters=filters.ChatType.PRIVATE)
        ],
        states={
            1: [CallbackQueryHandler(callback=private_review, pattern="next_post")],
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
