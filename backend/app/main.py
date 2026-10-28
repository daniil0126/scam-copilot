from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from dotenv import load_dotenv
from app.checks import router as checks_router
from app.db import Base, engine
from app.paypal import router as paypal_router
from app import models
import os

app = FastAPI()

load_dotenv()
PROJECT_ID = os.getenv('PROJECT_ID')

app.add_middleware(CORSMiddleware, allow_origins=[f"chrome-extension://{PROJECT_ID}"], allow_methods=["*"], allow_headers=["*"])

Base.metadata.create_all(engine)
app.include_router(paypal_router)
app.include_router(checks_router)

@app.get("/health")
def health():
    return {"status": "ok"}
