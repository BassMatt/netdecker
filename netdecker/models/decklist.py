from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Decklist(Base):
    """
    Represents a tracked decklist with basic metadata.
    """

    __tablename__ = "decklists"

    id: Mapped[int] = mapped_column(Integer(), nullable=False, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Timestamps - updated_at serves as both creation and last sync time
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship to deck cards
    deck_entries: Mapped[list["DeckEntry"]] = relationship(
        "DeckEntry", back_populates="decklist", cascade="all, delete-orphan"
    )


class DeckEntry(Base):
    """
    Represents cards in a decklist with quantities.
    Simple model to track what cards are in each deck.
    """

    __tablename__ = "deck_entries"

    id: Mapped[int] = mapped_column(Integer(), nullable=False, primary_key=True)
    decklist_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("decklists.id"), nullable=False, index=True
    )
    card_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)

    # Relationship back to decklist
    decklist: Mapped["Decklist"] = relationship(
        "Decklist", back_populates="deck_entries"
    )

    # Index for efficient lookups
    __table_args__ = (Index("idx_decklist_card", "decklist_id", "card_name"),)
