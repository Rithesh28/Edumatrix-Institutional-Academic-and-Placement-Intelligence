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
    # Check for jobs approaching deadline daily at 9:00 AM IST
    "check-application-deadlines-daily": {
        "task": "placement_tasks.check_application_deadlines",
        "schedule": crontab(hour=9, minute=0),
        "args": (3,),
    },
    # Close expired job postings hourly
    "close-expired-jobs-hourly": {
        "task": "placement_tasks.close_expired_jobs",
        "schedule": crontab(minute=0),
    },
    # Cleanup expired academic reminders daily at 3:00 AM IST
    "cleanup-expired-reminders-daily": {
        "task": "app.tasks.reminder_tasks.cleanup_expired_reminders",
        "schedule": crontab(hour=3, minute=0),
    },
}

if __name__ == "__main__":
    celery_app.start()