from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(Integer(), nullable=False, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, unique=True
    )
    quantity: Mapped[int] = mapped_column(Integer(), nullable=False)
    available: Mapped[int] = mapped_column(Integer(), nullable=False)
