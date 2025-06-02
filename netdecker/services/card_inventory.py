from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from netdecker.errors import CardInsufficientQuantityError
from netdecker.models.card import Card


class CardInventoryService:
    """
    Service for managing card inventory (owned/available quantities).
    Focused on pure inventory operations without allocation logic.
    """

    def __init__(self, sessionmaker_: sessionmaker[Session]) -> None:
        self.Session: sessionmaker[Session] = sessionmaker_

    def add_cards(self, card_quantities: dict[str, int]) -> None:
        """Add cards to inventory (both owned and available)."""
        card_list = [
            Card(name=name, quantity_owned=qty, quantity_available=qty)
            for name, qty in card_quantities.items()
        ]

        with self.Session.begin() as session:
            for card in card_list:
                insert_stmt = sqlite_insert(Card).values(
                    name=card.name,
                    quantity_owned=card.quantity_owned,
                    quantity_available=card.quantity_available,
                )
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[Card.name],
                    set_={
                        "quantity_owned": Card.__table__.c.quantity_owned
                        + insert_stmt.excluded.quantity_owned,
                        "quantity_available": Card.__table__.c.quantity_available
                        + insert_stmt.excluded.quantity_available,
                    },
                )
                session.execute(upsert_stmt)

    def remove_cards(self, card_quantities: dict[str, int]) -> None:
        """Remove cards from inventory completely."""
        with self.Session.begin() as session:
            for card_name, remove_count in card_quantities.items():
                card = session.scalars(
                    select(Card).where(Card.name == card_name)
                ).first()
                if not card:
                    continue

                if remove_count > card.quantity_owned:
                    raise CardInsufficientQuantityError(
                        name=card.name,
                        requested=remove_count,
                        quantity=card.quantity_owned,
                    )

                card.quantity_owned -= remove_count
                if card.quantity_owned < card.quantity_available:
                    card.quantity_available = card.quantity_owned

    def get_card(self, card_name: str) -> Card | None:
        """Get a card by name."""
        with self.Session() as session:
            return session.scalars(select(Card).where(Card.name == card_name)).first()

    def list_all_cards(self) -> list[Card]:
        """Get all cards in inventory."""
        with self.Session() as session:
            cards = session.scalars(select(Card)).all()
            session.expunge_all()
            return list(cards)

    def get_available_quantity(self, card_name: str) -> int:
        """Get available quantity for a specific card."""
        card = self.get_card(card_name)
        return card.quantity_available if card else 0

    def get_owned_quantity(self, card_name: str) -> int:
        """Get owned quantity for a specific card."""
        card = self.get_card(card_name)
        return card.quantity_owned if card else 0
