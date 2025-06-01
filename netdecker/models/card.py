from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Card(Base):
    """
    Represents proxy cards you own/have available.
    Simple model focused on tracking quantities for ordering decisions.
    """

    __tablename__ = "proxy_cards"

    id: Mapped[int] = mapped_column(Integer(), nullable=False, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    # Quantities
    quantity_owned: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    quantity_available: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
