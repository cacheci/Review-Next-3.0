from sqlalchemy import text

from src.database.posts import get_post_db
from src.database.users import get_users_db
from src.logger import scheduler_logger


async def sync_database():
    """
    清理/同步/提交WAL更改
    """
    async with get_users_db() as session:
        await session.execute(text('PRAGMA wal_checkpoint(FULL)'))
        await session.execute(text('PRAGMA optimize'))
        await session.commit()

    async with get_post_db() as session:
        await session.execute(text('PRAGMA wal_checkpoint(FULL)'))
        await session.execute(text('PRAGMA optimize'))
        await session.commit()

    scheduler_logger.info("Database synchronized and WAL changes committed.")

def clean_memory():
    """
    清理内存
    """
    import gc
    gc.collect()
    scheduler_logger.info("Memory cleaned.")