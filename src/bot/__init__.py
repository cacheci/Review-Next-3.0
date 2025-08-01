from functools import wraps

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.database.users import get_users_db, BannedUserModel, SubmitterModel, ReviewerModel


def check_banned(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        async with get_users_db() as session:
            async with session.begin():
                eff_user = update.effective_user
                result = await session.execute(select(BannedUserModel).filter_by(user_id=eff_user.id))
                result = result.scalar_one_or_none()
                if result:
                    await update.message.reply_text("您已被禁止使用此功能，请联系频道管理员。")
                    return
                result = await session.execute(select(SubmitterModel).filter_by(user_id=eff_user.id))
                submitter = result.scalar_one_or_none()
                if not submitter:
                    submitter = SubmitterModel(user_id=eff_user.id,
                                               username=eff_user.username,
                                               fullname=eff_user.full_name)
                else:
                    submitter.username = eff_user.username
                    submitter.fullname = eff_user.full_name
                await session.merge(submitter)

        return await func(update, context, *args, **kwargs)

    return wrapper


def check_reviewer(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        async with get_users_db() as session:
            query = update.callback_query
            eff_user = update.effective_user
            result = await session.execute(select(ReviewerModel).filter_by(user_id=eff_user.id))
            result = result.scalar_one_or_none()
            if result:
                return await func(update, context, *args, **kwargs)
            else:
                if query:
                    await query.answer("❗️您不是审核员，无法执行此操作。")
                else:
                    await update.message.reply_text("❗️您不是审核员，无法执行此操作。")

    return wrapper
