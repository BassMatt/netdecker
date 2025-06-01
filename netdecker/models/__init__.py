from .card import Card
from .decklist import DeckEntry, Decklist


def register_models() -> list:
    return [Card, Decklist, DeckEntry]
