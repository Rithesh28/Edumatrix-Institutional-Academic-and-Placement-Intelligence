"""
Celery App Configuration
"""

from celery import Celery
from celery.schedules import crontab
import os

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Create Celery app
celery_app = Celery(
    "edumatrix",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.reminder_tasks",
        "app.tasks.duty_tasks",
        "app.tasks.file_tasks",
        "app.tasks.placement_tasks",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,  # 1 hour
    broker_connection_retry_on_startup=True,
)

# Configure beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Reminder tasks are scheduled dynamically
    # Add periodic tasks here if needed
    # 'cleanup-task': {
    #     'task': 'app.tasks.cleanup',
    #     'schedule': crontab(hour=2, minute=0),
    # },
}

if __name__ == "__main__":
    celery_app.start()