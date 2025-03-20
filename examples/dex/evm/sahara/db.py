from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column
from examples.utils.db import BaseAccount


class Base(DeclarativeBase):
    pass


class SaharaAccount(Base, BaseAccount):
    account_id: Mapped[int]
    private: Mapped[str]
    proxy: Mapped[str]
    session_token: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f'{self.account_id} | {self.proxy}'
