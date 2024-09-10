from sqlalchemy import String, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BasehuntState(Base):
    __tablename__ = 'states'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    usdc_collected: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self):
        return (
            f'State(id={self.id}, address={self.address}, points={self.points}, usdc_collected={self.usdc_collected}, '
            f'referral_code={self.referral_code})'
        )

    def __str__(self):
        return repr(self)
