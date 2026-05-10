"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.config import settings
from app.logging_config import setup_logging


@worker_process_init.connect
def _setup_worker_logging(**_: object) -> None:
    # Ранняя валидация — прерываем старт воркера, если БД/Redis не настроены.
    settings.require("database_url")
    settings.require("redis_url")
    setup_logging()

celery = Celery(
    "vpnbox",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

celery.conf.beat_schedule = {
    "check-pending-payments": {
        "task": "app.worker.tasks.check_pending_payments",
        "schedule": 30.0,  # каждые 30 секунд
    },
    "expire-subscriptions": {
        "task": "app.worker.tasks.expire_subscriptions",
        "schedule": 60.0,  # каждую минуту
    },
    "send-expiry-reminders": {
        "task": "app.worker.tasks.send_expiry_reminders",
        "schedule": crontab(minute="*/30"),  # каждые 30 минут
    },
    "healthcheck-vpn-servers": {
        "task": "app.worker.tasks.healthcheck_servers",
        "schedule": 300.0,  # каждые 5 минут
    },
    "cleanup-stale-payments": {
        "task": "app.worker.tasks.cleanup_stale_payments",
        "schedule": crontab(hour="3", minute="0"),  # в 3:00 UTC ежедневно
    },
}
