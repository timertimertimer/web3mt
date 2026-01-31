from datetime import datetime, UTC

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from examples.utils.db import ProfileAccount


class Base(DeclarativeBase):
    pass


class CysicAccount(Base, ProfileAccount):
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC))
    ip: Mapped[str] = mapped_column(nullable=True)
    verifier_name: Mapped[str] = mapped_column(nullable=True)


CONNECTION_STRING = 'sqlite+aiosqlite:///./cysic.db'
