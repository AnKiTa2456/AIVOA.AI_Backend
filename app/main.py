from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import chat, hcps, interactions
from app.seed import seed_hcps

app = FastAPI(title="AI-First HCP CRM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(interactions.router)
app.include_router(hcps.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_hcps()


@app.get("/")
def root():
    return {"status": "ok", "service": "AI-First HCP CRM API"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}
