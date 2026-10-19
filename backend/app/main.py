from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import (
    auth_router,
    chat_router,
    circulars_router,
    notifications_router,
    upload_router,
    ai_router,
    reminders_router,
    profile_router,
    resume_analyzer_router,
    exam_duties_router,
    files_router,
    placement_router,
    recruitment_circulars_router,
    recruitment_results_router,
    admin_router,
    study_buddy_router
)
from contextlib import asynccontextmanager
import logging
from sqlalchemy import text
from . import models
from .core.database import engine, Base

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables & auto-heal missing columns and enums
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        with engine.connect() as conn:
            # Ensure venue column exists in exam_duties table for existing PostgreSQL volumes
            conn.execute(text("ALTER TABLE exam_duties ADD COLUMN IF NOT EXISTS venue VARCHAR;"))
            
            # Ensure chat_messages has AI support columns and nullable sender/receiver
            try:
                conn.execute(text("ALTER TABLE chat_messages ALTER COLUMN sender_id DROP NOT NULL;"))
                conn.execute(text("ALTER TABLE chat_messages ALTER COLUMN receiver_id DROP NOT NULL;"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS is_ai BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS ai_participant VARCHAR(50);"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS intent VARCHAR(50);"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS intent_confidence FLOAT;"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS sentiment VARCHAR(50);"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS sentiment_confidence FLOAT;"))
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS ai_metadata JSON;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_is_ai ON chat_messages (is_ai);"))
            except Exception as chat_mig_err:
                logger.warning(f"⚠️ chat_messages AI column check: {chat_mig_err}")
                
            conn.commit()
        logger.info("✅ Database tables created/verified successfully with all schema migrations")
    except Exception as e:
        logger.warning(f"⚠️ Database table creation/migration: {e}")

    # Background pre-warming of shared AI models to eliminate first-query cold start latency
    def _warmup_ai_models():
        try:
            from .services.embedding_service import embedding_service
            from .services.ai_generator_service import ai_generator
            logger.info("🔥 Starting background pre-warming of AI models...")
            embedding_service._ensure_model()
            ai_generator._ensure_model()
            logger.info("✅ AI models pre-warmed and ready for inference")
        except Exception as warmup_err:
            logger.warning(f"⚠️ AI model pre-warming encountered an issue: {warmup_err}")

    import threading
    threading.Thread(target=_warmup_ai_models, daemon=True).start()

    yield

# Initialize FastAPI app
app = FastAPI(
    title="EduMatrix API",
    description="AI-Powered College Communication & Career Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    errors = exc.errors()
    logger.warning(f"⚠️ Validation error on {request.url.path}: {errors}")
    error_messages = []
    for err in errors:
        loc = " -> ".join([str(x) for x in err.get("loc", []) if str(x) != "body"])
        msg = err.get("msg", "Invalid value")
        error_messages.append(f"{loc}: {msg}" if loc else msg)
    
    clean_msg = ", ".join(error_messages) if error_messages else "Invalid input data"
    return JSONResponse(
        status_code=422,
        content={"detail": clean_msg, "errors": jsonable_encoder(errors)}
    )

# Register routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(circulars_router)
app.include_router(notifications_router)
app.include_router(upload_router)
app.include_router(ai_router)
app.include_router(reminders_router)
app.include_router(profile_router)
app.include_router(resume_analyzer_router)
app.include_router(exam_duties_router)
app.include_router(files_router)
app.include_router(files_router, prefix="/api/v1")
app.include_router(placement_router)
app.include_router(placement_router, prefix="/api/v1")
app.include_router(recruitment_circulars_router)
app.include_router(recruitment_circulars_router, prefix="/api/v1")
app.include_router(recruitment_results_router)
app.include_router(recruitment_results_router, prefix="/api/v1")
app.include_router(admin_router)
app.include_router(study_buddy_router)
app.include_router(study_buddy_router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to EduMatrix API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}