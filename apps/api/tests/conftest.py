"""Shared test setup: every test gets a clean schema on the shared engine.

The app binds a single module-level async engine at import (app/db/base.py), so
tests share one database. This autouse fixture drops and recreates all tables
before each test, making the suite order-independent and free of cross-test
state bleed (e.g. duplicate-email 409s)."""
import asyncio
import os

# Deterministic, isolated test DB + offline stub LLM for the whole suite.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_suite.db")
os.environ.setdefault("LLM_PROVIDER", "stub")

import pytest


@pytest.fixture(autouse=True)
def _clean_schema():
    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base, engine

    async def reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(reset())
    yield
