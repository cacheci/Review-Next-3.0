from contextlib import asynccontextmanager
from enum import Enum
from typing import AsyncGenerator, Any

from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config import Config
from src.database import create_database
from src.logger import db_logger


class PostBase(AsyncAttrs, DeclarativeBase):
    pass


class PostStatus(Enum):
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
    NEED_REASON = 3


class PostModel(PostBase):
    # 稿件数据
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment='稿件id')
    text: Mapped[str] = mapped_column(String, nullable=True, comment='稿件内容')
    attachment: Mapped[str] = mapped_column(String, nullable=True, comment='稿件附件(json内容)')
    submitter_id: Mapped[int] = mapped_column(Integer, comment='投稿者id')
    status: Mapped[int] = mapped_column(Integer, default=PostStatus.PENDING.value, comment='稿件状态')
    submitter_msg_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='投稿者消息id')
    review_msg_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='审核群内消息id')
    operate_msg_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='操作消息id')
    publish_msg_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='发布消息id')  # 如果是拒稿的话，那么就是拒稿频道的id
    other: Mapped[str] = mapped_column(String, nullable=True, comment='其他信息(json内容)')
    created_at: Mapped[int] = mapped_column(Integer, nullable=True, comment='创建时间')
    finish_at: Mapped[int] = mapped_column(Integer, nullable=True, comment='审核完成时间')


class VoteType(Enum):
    APPROVE = 1
    REJECT = 2
    APPROVE_NSFW = 3


class PostLogModel(PostBase):
    # 稿件审核日志
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True, comment='日志id')
    post_id: Mapped[int] = mapped_column(Integer, index=True, autoincrement=True, comment='稿件id')
    reviewer_id: Mapped[int] = mapped_column(Integer, nullable=True, comment='审核者id')
    vote: Mapped[int] = mapped_column(Integer, nullable=True, comment='投票类型')
    operate_type: Mapped[str] = mapped_column(String, nullable=True, comment='操作来源 reviewer/system')
    operate_time: Mapped[int] = mapped_column(Integer, default=0, comment='操作时间')
    msg: Mapped[str] = mapped_column(String, nullable=True, comment='通过/拒绝理由')


create_database("posts", PostBase)
DATABASE_URL = f'sqlite+aiosqlite:///{Config.DATABASES_DIR / "posts.db"}'
ENGINE = create_async_engine(DATABASE_URL, echo=Config.SQLALCHEMY_LOG)
PostsSessionFactory = async_sessionmaker(bind=ENGINE, expire_on_commit=False)

@asynccontextmanager
async def get_post_db() -> AsyncGenerator[AsyncSession, Any]:
    async with PostsSessionFactory() as session:
        try:
            yield session
        except Exception as e:
            db_logger.error(f"Error in get_post_db: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
