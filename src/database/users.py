from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config import Config
from src.database import create_database
from src.logger import db_logger


class Base(AsyncAttrs, DeclarativeBase):
    pass


class ReviewerModel(Base):
    __tablename__ = "reviewers"  # 审核者数据
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment='用户id')
    username: Mapped[str] = mapped_column(String, nullable=True, comment="用户名")
    fullname: Mapped[str] = mapped_column(String, nullable=True, comment="TG全名")
    approve_count: Mapped[int] = mapped_column(Integer, default=0, comment='通过稿件数量')
    reject_count: Mapped[int] = mapped_column(Integer, default=0, comment='拒绝稿件数量')
    approve_but_rejected_count: Mapped[int] = mapped_column(Integer, default=0, comment='通过但是最后被拒绝的稿件数量')
    reject_but_approved_count: Mapped[int] = mapped_column(Integer, default=0, comment='拒绝但是最后通过的稿件数量')
    last_time: Mapped[int] = mapped_column(Integer, default=0, comment='最后审核时间')


class SubmitterModel(Base):
    __tablename__ = "submitters"  # 投稿者数据
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment='用户id')
    username: Mapped[str] = mapped_column(String, nullable=True, comment="用户名")
    fullname: Mapped[str] = mapped_column(String, nullable=True, comment="TG全名")
    submission_count: Mapped[int] = mapped_column(Integer, default=0, comment='投稿数量')
    approved_count: Mapped[int] = mapped_column(Integer, default=0, comment='通过数量')
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, comment='拒绝数量')


class BannedUserModel(Base):
    __tablename__ = "banned_users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment='用户id')
    username: Mapped[str] = mapped_column(String, nullable=True, comment="用户名")
    fullname: Mapped[str] = mapped_column(String, nullable=True, comment="TG全名")
    banned_reason: Mapped[str] = mapped_column(String(50), nullable=True, comment='封禁原因')
    banned_date: Mapped[int] = mapped_column(Integer, default=0, comment='封禁日期')
    banned_by: Mapped[int] = mapped_column(Integer, comment='封禁操作人ID')


create_database("users", Base)
DATABASE_URL = f'sqlite+aiosqlite:///{Config.DATABASES_DIR / "users.db"}'
ENGINE = create_async_engine(DATABASE_URL, echo=Config.SQLALCHEMY_LOG)
UsersSessionFactory = async_sessionmaker(bind=ENGINE, expire_on_commit=False)

@asynccontextmanager
async def get_users_db() -> AsyncGenerator[AsyncSession, Any]:
    async with UsersSessionFactory() as session:
        try:
            yield session
        except Exception as e:
            db_logger.error(f"Error in get_users_db: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


class UserOperation:
    @staticmethod
    async def submitter_add_count(user_id: int):
        async with UsersSessionFactory() as session:
            async with session.begin():
                submitter = await session.execute(select(SubmitterModel).filter_by(user_id=user_id))
                submitter = submitter.scalar_one_or_none()
                if not submitter:
                    submitter = SubmitterModel(user_id=user_id, submission_count=0)
                submitter.submission_count += 1
                await session.merge(submitter)

    @staticmethod
    async def get_reviewer(user_id: int) -> ReviewerModel | None:
        async with UsersSessionFactory() as session:
            reviewer = await session.execute(select(ReviewerModel).filter_by(user_id=user_id))
            return reviewer.scalar_one_or_none()
