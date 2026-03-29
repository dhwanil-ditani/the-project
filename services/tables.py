from sqlalchemy import MetaData, Table, engine, select
from sqlalchemy.orm import Session

from db.config import engine
from db.models import Base


def list_records(table_name: str, session: Session, limit: int = 10, offset: int = 0):
    table = Table(table_name, Base.metadata, autoload_with=engine)

    stmt = select(table).limit(limit).offset(offset)
    records = session.execute(stmt).all()
    column_names = table.columns.keys()
    data = [dict(zip(column_names, row)) for row in records]
    return data


def get_record(table_name: str, id: int, session: Session):
    table = Table(table_name, Base.metadata, autoload_with=engine)

    stmt = select(table).where(table.c.id == id)
    record = session.execute(stmt).first()
    if record:
        column_names = table.columns.keys()
        return dict(zip(column_names, record))
    return None


def patch_update_record(table_name: str, id: int, session: Session):
    pass


def put_update_record(table_name: str, id: int, session: Session):
    pass


def insert_record(table_name: str, session: Session):
    pass
