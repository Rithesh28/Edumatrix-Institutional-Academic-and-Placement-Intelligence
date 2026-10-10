from .auth import router as auth_router
from .chat import router as chat_router
from .circulars import router as circulars_router
from .notifications import router as notifications_router
from .upload import router as upload_router
from .ai import router as ai_router
from .reminders import router as reminders_router
from .profile import router as profile_router
from .resume_analyzer import router as resume_analyzer_router
from .exam_duties import router as exam_duties_router
from .files import router as files_router
from .placement import router as placement_router
from .admin import router as admin_router


__all__ = [
    "auth_router",
    "chat_router",
    "circulars_router",
    "notifications_router",
    "upload_router",
    "ai_router",
    "reminders_router",
    "profile_router",
    'resume_analyzer_router',
    "exam_duties_router",
    "files_router",
    'placement_router',
    "admin_router"
]