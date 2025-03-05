from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import create_engine, select, inspect
from models import Card, Base
from errors import CardInsufficientAvailable, CardInsufficientQuantity

class SQLiteStore:
    def __init__(self, conn_string: str):
        self.engine=create_engine(conn_string)
        self.Session = sessionmaker(self.engine)

        # create table if doesn't exist
        ins = inspect(self.engine)
        if not ins.has_table("cards"):
            Base.metadata.create_all(self.engine)

    def add_cards(self, card_list: dict[str, int]):
        """
        Upserts Loan Objects into database, edits quantity if present
        """
        
        with self.Session.begin() as session:
            for card_name, card_quantity in card_list.items():
                insert_stmt = insert(Card).values(
                    name=card_name,
                    quantity=card_quantity,
                    available=card_quantity
                )
                do_update_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[Card.name],
                    set_=dict(quantity=Card.quantity+insert_stmt.excluded.quantity),
                    set_=dict(available=Card.available + insert_stmt.excluded.quantity)
                )
                session.execute(do_update_stmt)
    
    def delete_cards(self, card_list: dict[str, int]) -> int:
        """
        Removes cards from quantity, available.
        """
        with self.Session.begin() as session:
            for card_name, remove_count in card_list.items():
                card = session.scalars(select(Card).where(Card.name == card_name)).first()
                if remove_count > card.quantity:
                    raise CardInsufficientQuantity(name=card.name, requested=remove_count, available=card.available)
                card.quantity -= remove_count
                if card.quantity < card.available:
                    card.available = card.quantity

    def use_cards(self, card_list: dict[str, int]) -> int:
        """
        Marks cards as not available, throws error if amount requested to use exceeds amount available. 
        """
        with self.Session.begin() as session:
            for card_name, use_count in card_list.items():
                card = session.scalars(select(Card).where(Card.name == card_name)).first()
                if use_count > card.available:
                    raise CardInsufficientAvailable(name=card.name, requested=use_count, available=card.available)
                card.available -= use_count 

    def free_cards(self, card_list: dict[str, int]) -> int:
        """
        Marks cards as available, throws error if amount freed exceeds quantity 
        """
        with self.Session.begin() as session:
            for card_name, free_count in card_list.items():
                card = session.scalars(select(Card).where(Card.name == card_name)).first()
                if card.available + free_count > card.quantity:
                    raise CardInsufficientQuantity(name=card.name, requested=free_count, available=card.available)
                card.available += free_count
    
    def get_card(self, card_name: str) -> Card:
        with self.Session.begin() as session:
            return session.scalars(select(Card).where(Card.name == card_name)).first()

    def list_cards(self):
        """
        Returns all cards in proxy list database
        """
        with self.Session.begin() as session:
            cards = session.scalars(select(Card)).all()
            session.expunge_all()
            return cards






