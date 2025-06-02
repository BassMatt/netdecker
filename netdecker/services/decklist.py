from sqlalchemy.orm import Session, sessionmaker

from netdecker.models.decklist import DeckEntry, Decklist


class DecklistService:
    """
    Service for managing decklists and their card entries.
    Focused on pure CRUD operations without allocation logic.
    """

    def __init__(self, sessionmaker_: sessionmaker[Session]) -> None:
        self.Session: sessionmaker[Session] = sessionmaker_

    def get_decklist(self, name: str, format_name: str) -> Decklist | None:
        """Get a decklist by name and format."""
        with self.Session() as session:
            return (
                session.query(Decklist)
                .filter(Decklist.name == name, Decklist.format == format_name)
                .first()
            )

    def get_decklist_by_name(self, name: str) -> Decklist | None:
        """Get a decklist by name only (backward compatibility method)."""
        with self.Session() as session:
            return session.query(Decklist).filter(Decklist.name == name).first()

    def get_decklist_by_id(self, decklist_id: int) -> Decklist | None:
        """Get a decklist by ID."""
        with self.Session() as session:
            return session.query(Decklist).filter(Decklist.id == decklist_id).first()

    def get_decklist_cards(self, decklist_id: int) -> dict[str, int]:
        """Get all cards in a decklist as a name->quantity dictionary."""
        with self.Session() as session:
            entries = (
                session.query(DeckEntry)
                .filter(DeckEntry.decklist_id == decklist_id)
                .all()
            )
            return {entry.card_name: entry.quantity for entry in entries}

    def create_decklist(
        self, name: str, format_name: str, url: str | None = None
    ) -> int:
        """Create a new decklist and return its ID."""
        with self.Session.begin() as session:
            decklist = Decklist(name=name, format=format_name, url=url)
            session.add(decklist)
            session.flush()  # Get ID without committing
            return decklist.id

    def delete_decklist(self, decklist_id: int) -> bool:
        """
        Delete a decklist and all its associated deck entries.
        Returns True if successful, False if decklist not found.
        Note: This does NOT handle card allocation - use CardAllocationService for that.
        """
        with self.Session.begin() as session:
            decklist = (
                session.query(Decklist).filter(Decklist.id == decklist_id).first()
            )
            if not decklist:
                return False

            # Delete the decklist, will cascade delete all DeckEntry
            session.query(Decklist).filter(Decklist.id == decklist_id).delete()
            return True

    def update_decklist_cards(
        self, decklist_id: int, new_card_list: dict[str, int]
    ) -> None:
        """
        Update a decklist with new cards, replacing all existing entries.
        Note: This does NOT handle card allocation - use CardAllocationService for that.
        """
        with self.Session.begin() as session:
            # Clear existing deck entries
            session.query(DeckEntry).filter(
                DeckEntry.decklist_id == decklist_id
            ).delete()

            # Add new deck entries
            for card_name, quantity in new_card_list.items():
                entry = DeckEntry(
                    decklist_id=decklist_id, card_name=card_name, quantity=quantity
                )
                session.add(entry)

    def list_decklists(self) -> list[Decklist]:
        """Get all decklists."""
        with self.Session() as session:
            decklists = session.query(Decklist).all()
            session.expunge_all()  # Handle object detachment
            return decklists

    def update_decklist_url(self, decklist_id: int, new_url: str) -> bool:
        """
        Update a decklist's URL.
        Returns True if successful, False if decklist not found.
        """
        with self.Session.begin() as session:
            decklist = (
                session.query(Decklist).filter(Decklist.id == decklist_id).first()
            )
            if not decklist:
                return False
            decklist.url = new_url
            return True

    def update_decklist_metadata(
        self,
        decklist_id: int,
        name: str | None = None,
        format_name: str | None = None,
        url: str | None = None,
    ) -> bool:
        """
        Update decklist metadata.
        Returns True if successful, False if decklist not found.
        """
        with self.Session.begin() as session:
            decklist = (
                session.query(Decklist).filter(Decklist.id == decklist_id).first()
            )
            if not decklist:
                return False

            if name is not None:
                decklist.name = name
            if format_name is not None:
                decklist.format = format_name
            if url is not None:
                decklist.url = url

            return True
