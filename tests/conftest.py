import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Must be set before importing anything that loads settings
os.environ["APP_ENV"] = "testing"

from main import app
from db.models import Base
from db.config import engine, async_session, get_db

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture
async def async_client(db_session):
    async def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
