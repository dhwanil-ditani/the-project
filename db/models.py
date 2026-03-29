from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tables(Base):
    __tablename__ = "sys_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    label: Mapped[str] = mapped_column()


class Columns(Base):
    __tablename__ = "sys_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    label: Mapped[str] = mapped_column()
    data_type: Mapped[str] = mapped_column()
