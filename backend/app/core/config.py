import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # Admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@edumatrix.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin123")
    
    # API Keys (optional, for later)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")

    # AI Chat Assistant Configuration
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
    AI_MODEL_PATH: str = os.getenv("AI_MODEL_PATH", "")
    AI_MAX_NEW_TOKENS: int = int(os.getenv("AI_MAX_NEW_TOKENS", "256"))
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.2"))
    AI_ASSISTANT_NAME: str = os.getenv("AI_ASSISTANT_NAME", "EduMatrix AI Assistant")

    # Study Buddy Configuration
    STUDY_BUDDY_MIN_RELEVANCE_SCORE: float = float(os.getenv("STUDY_BUDDY_MIN_RELEVANCE_SCORE", "0.35"))
    STUDY_BUDDY_TOP_K: int = int(os.getenv("STUDY_BUDDY_TOP_K", "4"))
    STUDY_BUDDY_MAX_CONTEXT_CHARS: int = int(os.getenv("STUDY_BUDDY_MAX_CONTEXT_CHARS", "2000"))
    
    # Firebase
    FIREBASE_CREDENTIALS: str = os.getenv("FIREBASE_CREDENTIALS", "")
    
    # Email Configuration
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "False").lower() == "true"
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER: str = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@edumatrix.com")
    
    # Resend API
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    
    # ============================================
    # NEW: MinIO Configuration
    # ============================================
    MINIO_HOST: str = os.getenv("MINIO_HOST", "minio")
    MINIO_PORT: int = int(os.getenv("MINIO_PORT", "9000"))
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    MINIO_BUCKETS: List[str] = os.getenv("MINIO_BUCKETS", "exam-duties,assignments,circulars,resumes,timetables,certificates,placement-docs,syllabus,lecture-notes").split(",")
    
    @property
    def MINIO_ENDPOINT(self) -> str:
        """Get MinIO endpoint URL"""
        scheme = "https" if self.MINIO_SECURE else "http"
        return f"{scheme}://{self.MINIO_HOST}:{self.MINIO_PORT}"
    
    # ============================================
    # NEW: Qdrant Configuration
    # ============================================
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "qdrant")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "files")
    QDRANT_VECTOR_SIZE: int = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))
    
    @property
    def QDRANT_URL(self) -> str:
        """Get Qdrant URL"""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    # ============================================
    # NEW: File Upload Configuration
    # ============================================
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB default
    ALLOWED_EXTENSIONS: List[str] = os.getenv(
        "ALLOWED_EXTENSIONS",
        ".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.csv,.jpg,.jpeg,.png,.txt"
    ).split(",")
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "image/jpeg",
        "image/png",
        "text/plain"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()