from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from netdecker.errors import CardInsufficientQuantityError
from netdecker.models.card import Card
from netdecker.models.decklist import DeckEntry


class CardAllocationService:
    """
    Service for managing card allocation between inventory and decklists.
    Handles the coordination between card availability and deck requirements.
    """

    def __init__(self, sessionmaker_: sessionmaker[Session]) -> None:
        self.Session: sessionmaker[Session] = sessionmaker_

    def allocate_cards(self, card_quantities: dict[str, int]) -> dict[str, int]:
        """
        Allocate cards (mark as unavailable).
        Returns dict of cards that couldn't be fully allocated.
        """
        insufficient_cards = {}

        with self.Session.begin() as session:
            for card_name, quantity_needed in card_quantities.items():
                card = session.scalars(
                    select(Card).where(Card.name == card_name)
                ).first()

                if not card:
                    insufficient_cards[card_name] = quantity_needed
                    continue

                if card.quantity_available < quantity_needed:
                    insufficient_cards[card_name] = (
                        quantity_needed - card.quantity_available
                    )
                    # Allocate what we can
                    card.quantity_available = 0
                else:
                    card.quantity_available -= quantity_needed

        return insufficient_cards

    def release_cards(self, card_quantities: dict[str, int]) -> None:
        """Release allocated cards back to available pool."""
        with self.Session.begin() as session:
            for card_name, quantity in card_quantities.items():
                card = session.scalars(
                    select(Card).where(Card.name == card_name)
                ).first()
                if not card:
                    continue

                new_available = card.quantity_available + quantity
                if new_available > card.quantity_owned:
                    raise CardInsufficientQuantityError(
                        name=card.name,
                        requested=quantity,
                        quantity=card.quantity_owned,
                    )
                card.quantity_available = new_available

    def calculate_needed_cards(self, required_cards: dict[str, int]) -> dict[str, int]:
        """Calculate which cards need to be ordered based on availability."""
        cards_needed = {}

        with self.Session() as session:
            for card_name, needed_quantity in required_cards.items():
                card = session.scalars(
                    select(Card).where(Card.name == card_name)
                ).first()

                if not card:
                    cards_needed[card_name] = needed_quantity
                elif card.quantity_available < needed_quantity:
                    cards_needed[card_name] = needed_quantity - card.quantity_available

        return cards_needed

    def check_allocation_feasibility(
        self, card_quantities: dict[str, int]
    ) -> dict[str, int]:
        """
        Check if cards can be allocated without actually doing it.
        Returns cards that would be insufficient.
        """
        insufficient_cards = {}

        with self.Session() as session:
            for card_name, quantity_needed in card_quantities.items():
                card = session.scalars(
                    select(Card).where(Card.name == card_name)
                ).first()

                if not card:
                    insufficient_cards[card_name] = quantity_needed
                elif card.quantity_available < quantity_needed:
                    insufficient_cards[card_name] = (
                        quantity_needed - card.quantity_available
                    )

        return insufficient_cards

    def get_current_deck_allocation(self, decklist_id: int) -> dict[str, int]:
        """Get the current card allocation for a specific decklist."""
        with self.Session() as session:
            entries = session.scalars(
                select(DeckEntry).where(DeckEntry.decklist_id == decklist_id)
            ).all()
            return {entry.card_name: entry.quantity for entry in entries}

    def release_decklist_allocation(self, decklist_id: int) -> None:
        """Release all cards allocated to a specific decklist."""
        with self.Session.begin() as session:
            entries = session.scalars(
                select(DeckEntry).where(DeckEntry.decklist_id == decklist_id)
            ).all()

            for entry in entries:
                card = session.scalars(
                    select(Card).where(Card.name == entry.card_name)
                ).first()
                if card:
                    card.quantity_available += entry.quantity
