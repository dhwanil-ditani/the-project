from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.config import engine
from db.models import Base
from routers import table_api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as session:
        session.execute(text(
            "INSERT INTO sys_tables (name, label) VALUES ('sys_tables', 'System Tables')"))
        session.execute(text(
            "INSERT INTO sys_tables (name, label) VALUES ('sys_columns', 'System Columns')"))
        session.commit()
    yield
    Base.metadata.drop_all(bind=engine)


app = FastAPI(lifespan=lifespan)


app.include_router(table_api_router, prefix="/api")
