from sqlalchemy.orm import Mapped, mapped_column


class BaseAccount:
    __tablename__ = 'accounts'
    id: Mapped[int] = mapped_column(primary_key=True)


class ProfileAccount(BaseAccount):
    profile_id: Mapped[int] = mapped_column(nullable=True)
    address: Mapped[str]
