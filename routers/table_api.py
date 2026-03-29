from fastapi import APIRouter

from db.config import SessionDep
from services import tables as tables_service

router = APIRouter(prefix="/table", tags=["Table API"])


@router.get("/{table_name}")
def list_records(table_name: str, session: SessionDep, limit: int = 10, offset: int = 0):
    return tables_service.list_records(table_name, session, limit, offset)


@router.get("/{table_name}/{id}")
def get_record(table_name: str, id: int, session: SessionDep):
    return tables_service.get_record(table_name, id, session)


@router.patch("/{table_name}/{id}")
def patch_update_record(table_name: str, id: int, session: SessionDep):
    pass


@router.put("/{table_name}/{id}")
def put_update_record(table_name: str, id: int, session: SessionDep):
    pass


@router.post("/{table_name}")
def insert_record(table_name: str, session: SessionDep):
    pass
