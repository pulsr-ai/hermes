from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.core.database import engine
from app.core.config import settings
from app.core.security import get_api_key
from app.models import email as models
from app.api import templates, emails, webhooks
from app.smtp.server import smtp_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    
    smtp_server.host = settings.SMTP_HOST
    smtp_server.port = settings.SMTP_PORT
    smtp_server.start()
    logger.info(f"SMTP server started on {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    
    yield
    
    smtp_server.stop()
    logger.info("SMTP server stopped")


app = FastAPI(
    title="Hermes Email Service",
    description="Transactional email service with SMTP receiver, templating, and webhooks",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    templates.router,
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    emails.router,
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    webhooks.router,
    dependencies=[Depends(get_api_key)]
)


@app.get("/")
def read_root():
    return {
        "service": "Hermes Email Service",
        "version": "1.0.0",
        "status": "running",
        "smtp_server": f"{settings.SMTP_HOST}:{settings.SMTP_PORT}"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}