from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IcloudEmail(Base):
    __tablename__ = 'emails'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[int] = mapped_column(Integer, unique=True)
    login: Mapped[str] = mapped_column(String(255), unique=True)

    def __repr__(self):
        return f'IcloudEmail(label={self.label}, name={self.login})'


CONNECTION_STRING = 'sqlite+aiosqlite:///./icloud.db'
