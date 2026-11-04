from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from dotenv import load_dotenv
from app.chat import router as chat_router
from app.access import install_access_token
from app.checks import router as checks_router
from app.db import Base, engine
from app.inbound import router as inbound_router
from app import llm_openrouter  # noqa: F401  registers the free-only OpenRouter provider
from app.monitor import lifespan, router as monitor_router
from app.notifications.router import router as notifications_router
from app.reports.router import router as reports_router
from app.security import install_log_scrubber
from app.webhooks import router as webhooks_router
from app.paypal import router as paypal_router
from app.stubs import ENABLED as STUBS_ENABLED, router as stubs_router
from app import models
import os

app = FastAPI(lifespan=lifespan)

load_dotenv()
install_log_scrubber()  # secrets never reach the logs (docs/plans/security-checklist.md, item 7)
PROJECT_ID = os.getenv('PROJECT_ID')

install_access_token(app)  # before CORS, so CORS stays outermost; no-op without ACCESS_TOKEN

app.add_middleware(CORSMiddleware, allow_origins=[f"chrome-extension://{PROJECT_ID}"], allow_methods=["*"], allow_headers=["*"])

Base.metadata.create_all(engine)
app.include_router(paypal_router)
app.include_router(checks_router)
app.include_router(chat_router)
app.include_router(monitor_router)
app.include_router(inbound_router)
app.include_router(webhooks_router)
app.include_router(notifications_router)
app.include_router(reports_router)
if STUBS_ENABLED:
    app.include_router(stubs_router)

@app.get("/health")
def health():
    return {"status": "ok"}
