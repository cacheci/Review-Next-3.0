"""
定时任务
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from .clean import clean_memory, sync_database
from ..logger import scheduler_logger


def start_scheduler():
    scheduler_logger.info("Starting scheduler...")
    scheduler = BackgroundScheduler()
    scheduler.add_job(clean_memory, 'cron', hour=2, minute=30, second=0)
    scheduler.start()

    async_scheduler = AsyncIOScheduler()
    async_scheduler.add_job(sync_database, 'cron', hour=3, minute=30, second=0)
    async_scheduler.start()
