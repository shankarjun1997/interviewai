from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, interviews
from app.db.base import Base, engine
from app.models import *  # noqa: F401,F403  (register models on Base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: create tables. Prod uses Alembic migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="InterviewAI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(interviews.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "interviewai-api"}
