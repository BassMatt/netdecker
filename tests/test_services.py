"""Tests for NetDecker service layer."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from netdecker.errors import CardInsufficientQuantityError
from netdecker.models.card import Card
from netdecker.models.decklist import DeckEntry, Decklist
from netdecker.services.allocation import CardAllocationService
from netdecker.services.card_inventory import CardInventoryService
from netdecker.services.decklist import DecklistService


class TestCardInventoryService:
    """Test cases for CardInventoryService."""

    @pytest.fixture
    def mock_sessionmaker(self):
        """Create a mock sessionmaker for testing."""
        mock_session = Mock(spec=Session)
        mock_sessionmaker = Mock(spec=sessionmaker)
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)
        return mock_sessionmaker

    @pytest.fixture
    def service(self, mock_sessionmaker):
        """Create a CardInventoryService instance with mocked sessionmaker."""
        return CardInventoryService(mock_sessionmaker)

    def test_init(self, mock_sessionmaker):
        """Test CardInventoryService initialization."""
        service = CardInventoryService(mock_sessionmaker)
        assert service.Session == mock_sessionmaker

    def test_add_cards_new_cards(self, service, mock_sessionmaker):
        """Test adding new cards to inventory."""
        card_quantities = {"Lightning Bolt": 4, "Counterspell": 2}

        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        service.add_cards(card_quantities)

        # Verify session.execute was called for each card
        assert mock_session.execute.call_count == 2

    def test_add_cards_empty_dict(self, service, mock_sessionmaker):
        """Test adding empty card dictionary."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        service.add_cards({})

        # Should not call execute for empty dict
        mock_session.execute.assert_not_called()

    def test_remove_cards_sufficient_quantity(self, service, mock_sessionmaker):
        """Test removing cards when sufficient quantity exists."""
        card_quantities = {"Lightning Bolt": 2}

        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock existing card
        existing_card = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=4
        )
        mock_session.scalars.return_value.first.return_value = existing_card

        service.remove_cards(card_quantities)

        # Verify card quantities were updated
        assert existing_card.quantity_owned == 2
        assert existing_card.quantity_available == 2

    def test_remove_cards_adjust_available_quantity(self, service, mock_sessionmaker):
        """Test removing cards adjusts available quantity when needed."""
        card_quantities = {"Lightning Bolt": 3}

        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock existing card with some cards already allocated
        existing_card = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )
        mock_session.scalars.return_value.first.return_value = existing_card

        service.remove_cards(card_quantities)

        # Available should be capped at new owned quantity
        assert existing_card.quantity_owned == 1
        assert existing_card.quantity_available == 1

    def test_remove_cards_insufficient_quantity(self, service, mock_sessionmaker):
        """Test removing more cards than owned raises exception."""
        card_quantities = {"Lightning Bolt": 5}

        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock existing card with insufficient quantity
        existing_card = Card(
            name="Lightning Bolt", quantity_owned=2, quantity_available=2
        )
        mock_session.scalars.return_value.first.return_value = existing_card

        with pytest.raises(CardInsufficientQuantityError) as exc_info:
            service.remove_cards(card_quantities)

        error = exc_info.value
        assert error.name == "Lightning Bolt"
        assert error.requested == 5
        assert error.quantity == 2

    def test_remove_cards_nonexistent_card(self, service, mock_sessionmaker):
        """Test removing nonexistent card is handled gracefully."""
        card_quantities = {"Nonexistent Card": 1}

        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock no card found
        mock_session.scalars.return_value.first.return_value = None

        # Should not raise exception
        service.remove_cards(card_quantities)

    def test_get_card_exists(self, service, mock_sessionmaker):
        """Test getting an existing card."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_card = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )
        mock_session.scalars.return_value.first.return_value = expected_card

        result = service.get_card("Lightning Bolt")

        assert result == expected_card

    def test_get_card_not_exists(self, service, mock_sessionmaker):
        """Test getting a nonexistent card returns None."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        mock_session.scalars.return_value.first.return_value = None

        result = service.get_card("Nonexistent Card")

        assert result is None

    def test_list_all_cards(self, service, mock_sessionmaker):
        """Test listing all cards in inventory."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_cards = [
            Card(name="Lightning Bolt", quantity_owned=4, quantity_available=2),
            Card(name="Counterspell", quantity_owned=2, quantity_available=1),
        ]
        mock_session.scalars.return_value.all.return_value = expected_cards

        result = service.list_all_cards()

        assert result == expected_cards
        mock_session.expunge_all.assert_called_once()

    def test_list_all_cards_empty(self, service, mock_sessionmaker):
        """Test listing cards when inventory is empty."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        mock_session.scalars.return_value.all.return_value = []

        result = service.list_all_cards()

        assert result == []

    @pytest.mark.parametrize(
        "card_name,expected_available",
        [
            ("Lightning Bolt", 4),
            ("Nonexistent Card", 0),
        ],
    )
    def test_get_available_quantity(
        self, service, mock_sessionmaker, card_name, expected_available
    ):
        """Test getting available quantity for cards."""
        with patch.object(service, "get_card") as mock_get_card:
            if expected_available > 0:
                mock_card = Card(
                    name=card_name,
                    quantity_owned=4,
                    quantity_available=expected_available,
                )
                mock_get_card.return_value = mock_card
            else:
                mock_get_card.return_value = None

            result = service.get_available_quantity(card_name)

            assert result == expected_available
            mock_get_card.assert_called_once_with(card_name)

    @pytest.mark.parametrize(
        "card_name,expected_owned",
        [
            ("Lightning Bolt", 4),
            ("Nonexistent Card", 0),
        ],
    )
    def test_get_owned_quantity(
        self, service, mock_sessionmaker, card_name, expected_owned
    ):
        """Test getting owned quantity for cards."""
        with patch.object(service, "get_card") as mock_get_card:
            if expected_owned > 0:
                mock_card = Card(
                    name=card_name, quantity_owned=expected_owned, quantity_available=2
                )
                mock_get_card.return_value = mock_card
            else:
                mock_get_card.return_value = None

            result = service.get_owned_quantity(card_name)

            assert result == expected_owned
            mock_get_card.assert_called_once_with(card_name)


class TestDecklistService:
    """Test cases for DecklistService."""

    @pytest.fixture
    def mock_sessionmaker(self):
        """Create a mock sessionmaker for testing."""
        mock_session = Mock(spec=Session)
        mock_sessionmaker = Mock(spec=sessionmaker)
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)
        return mock_sessionmaker

    @pytest.fixture
    def service(self, mock_sessionmaker):
        """Create a DecklistService instance with mocked sessionmaker."""
        return DecklistService(mock_sessionmaker)

    def test_init(self, mock_sessionmaker):
        """Test DecklistService initialization."""
        service = DecklistService(mock_sessionmaker)
        assert service.Session == mock_sessionmaker

    def test_get_decklist_found(self, service, mock_sessionmaker):
        """Test getting an existing decklist by name and format."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_deck = Decklist(
            name="Test Deck", format="Modern", url="http://test.com"
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            expected_deck
        )

        result = service.get_decklist("Test Deck", "Modern")

        assert result == expected_deck

    def test_get_decklist_not_found(self, service, mock_sessionmaker):
        """Test getting a nonexistent decklist returns None."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_decklist("Nonexistent", "Modern")

        assert result is None

    def test_get_decklist_by_name(self, service, mock_sessionmaker):
        """Test getting a decklist by name only."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_deck = Decklist(
            name="Test Deck", format="Modern", url="http://test.com"
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            expected_deck
        )

        result = service.get_decklist_by_name("Test Deck")

        assert result == expected_deck

    def test_get_decklist_by_id(self, service, mock_sessionmaker):
        """Test getting a decklist by ID."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_deck = Decklist(id=1, name="Test Deck", format="Modern")
        mock_session.query.return_value.filter.return_value.first.return_value = (
            expected_deck
        )

        result = service.get_decklist_by_id(1)

        assert result == expected_deck

    def test_get_decklist_cards(self, service, mock_sessionmaker):
        """Test getting cards from a decklist."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        mock_entries = [
            DeckEntry(decklist_id=1, card_name="Lightning Bolt", quantity=4),
            DeckEntry(decklist_id=1, card_name="Counterspell", quantity=2),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_entries
        )

        result = service.get_decklist_cards(1)

        expected = {"Lightning Bolt": 4, "Counterspell": 2}
        assert result == expected

    def test_create_decklist(self, service, mock_sessionmaker):
        """Test creating a new decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock the decklist to return an ID after flush
        mock_decklist = Mock()
        mock_decklist.id = 123

        def mock_add(decklist):
            # Simulate setting the ID after flush
            decklist.id = 123

        mock_session.add.side_effect = mock_add

        result = service.create_decklist("New Deck", "Modern", "http://example.com")

        assert result == 123
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_delete_decklist_exists(self, service, mock_sessionmaker):
        """Test deleting an existing decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_decklist = Decklist(id=1, name="Test Deck", format="Modern")
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_decklist
        )

        result = service.delete_decklist(1)

        assert result is True
        mock_session.query.return_value.filter.return_value.delete.assert_called_once()

    def test_delete_decklist_not_exists(self, service, mock_sessionmaker):
        """Test deleting a nonexistent decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_decklist(999)

        assert result is False

    def test_update_decklist_cards(self, service, mock_sessionmaker):
        """Test updating decklist cards."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        new_cards = {"Lightning Bolt": 4, "Counterspell": 2}

        service.update_decklist_cards(1, new_cards)

        # Should delete existing entries and add new ones
        mock_session.query.return_value.filter.return_value.delete.assert_called_once()
        assert mock_session.add.call_count == 2

    def test_list_decklists(self, service, mock_sessionmaker):
        """Test listing all decklists."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        expected_decks = [
            Decklist(name="Deck 1", format="Modern"),
            Decklist(name="Deck 2", format="Legacy"),
        ]
        mock_session.query.return_value.all.return_value = expected_decks

        result = service.list_decklists()

        assert result == expected_decks
        mock_session.expunge_all.assert_called_once()

    def test_update_decklist_url_exists(self, service, mock_sessionmaker):
        """Test updating URL for existing decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_decklist = Decklist(id=1, name="Test Deck", format="Modern")
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_decklist
        )

        result = service.update_decklist_url(1, "http://new-url.com")

        assert result is True
        assert mock_decklist.url == "http://new-url.com"

    def test_update_decklist_url_not_exists(self, service, mock_sessionmaker):
        """Test updating URL for nonexistent decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.update_decklist_url(999, "http://new-url.com")

        assert result is False

    @pytest.mark.parametrize(
        "name,format_name,url",
        [
            ("New Name", None, None),
            (None, "Legacy", None),
            (None, None, "http://new-url.com"),
            ("New Name", "Legacy", "http://new-url.com"),
        ],
    )
    def test_update_decklist_metadata(
        self, service, mock_sessionmaker, name, format_name, url
    ):
        """Test updating decklist metadata with various combinations."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_decklist = Decklist(
            id=1, name="Old Name", format="Modern", url="http://old.com"
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_decklist
        )

        result = service.update_decklist_metadata(
            1, name=name, format_name=format_name, url=url
        )

        assert result is True
        if name is not None:
            assert mock_decklist.name == name
        if format_name is not None:
            assert mock_decklist.format == format_name
        if url is not None:
            assert mock_decklist.url == url


class TestCardAllocationService:
    """Test cases for CardAllocationService."""

    @pytest.fixture
    def mock_sessionmaker(self):
        """Create a mock sessionmaker for testing."""
        mock_session = Mock(spec=Session)
        mock_sessionmaker = Mock(spec=sessionmaker)
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)
        return mock_sessionmaker

    @pytest.fixture
    def service(self, mock_sessionmaker):
        """Create a CardAllocationService instance with mocked sessionmaker."""
        return CardAllocationService(mock_sessionmaker)

    def test_init(self, mock_sessionmaker):
        """Test CardAllocationService initialization."""
        service = CardAllocationService(mock_sessionmaker)
        assert service.Session == mock_sessionmaker

    def test_allocate_cards_sufficient_inventory(self, service, mock_sessionmaker):
        """Test allocating cards when sufficient inventory exists."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock cards with sufficient availability
        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=4
        )
        counterspell = Card(name="Counterspell", quantity_owned=2, quantity_available=2)

        # Create a call counter to track which card to return
        call_count = [0]
        cards = [lightning_bolt, counterspell]

        def mock_scalars(query):
            mock_result = Mock()
            # Return the appropriate card based on call order
            card = cards[call_count[0]] if call_count[0] < len(cards) else None
            call_count[0] += 1
            mock_result.first.return_value = card
            return mock_result

        mock_session.scalars.side_effect = mock_scalars

        card_quantities = {"Lightning Bolt": 3, "Counterspell": 1}
        result = service.allocate_cards(card_quantities)

        # Should be no insufficient cards
        assert result == {}
        # Cards should be allocated
        assert lightning_bolt.quantity_available == 1
        assert counterspell.quantity_available == 1

    def test_allocate_cards_insufficient_inventory(self, service, mock_sessionmaker):
        """Test allocating cards when insufficient inventory exists."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock card with insufficient availability
        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )

        mock_session.scalars.return_value.first.return_value = lightning_bolt

        card_quantities = {"Lightning Bolt": 3}
        result = service.allocate_cards(card_quantities)

        # Should have 1 insufficient card
        assert result == {"Lightning Bolt": 1}
        # All available should be allocated
        assert lightning_bolt.quantity_available == 0

    def test_allocate_cards_nonexistent_card(self, service, mock_sessionmaker):
        """Test allocating nonexistent cards."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_session.scalars.return_value.first.return_value = None

        card_quantities = {"Nonexistent Card": 2}
        result = service.allocate_cards(card_quantities)

        # All cards should be insufficient
        assert result == {"Nonexistent Card": 2}

    def test_release_cards_valid(self, service, mock_sessionmaker):
        """Test releasing cards back to available pool."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )
        mock_session.scalars.return_value.first.return_value = lightning_bolt

        card_quantities = {"Lightning Bolt": 1}
        service.release_cards(card_quantities)

        # Available should increase
        assert lightning_bolt.quantity_available == 3

    def test_release_cards_exceeds_owned(self, service, mock_sessionmaker):
        """Test releasing more cards than owned raises exception."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=3
        )
        mock_session.scalars.return_value.first.return_value = lightning_bolt

        card_quantities = {"Lightning Bolt": 2}  # Would make available = 5 > owned = 4

        with pytest.raises(CardInsufficientQuantityError) as exc_info:
            service.release_cards(card_quantities)

        error = exc_info.value
        assert error.name == "Lightning Bolt"
        assert error.requested == 2
        assert error.quantity == 4

    def test_release_cards_nonexistent(self, service, mock_sessionmaker):
        """Test releasing nonexistent cards is handled gracefully."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        mock_session.scalars.return_value.first.return_value = None

        card_quantities = {"Nonexistent Card": 1}
        # Should not raise exception
        service.release_cards(card_quantities)

    def test_calculate_needed_cards(self, service, mock_sessionmaker):
        """Test calculating cards that need to be ordered."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        # Mock different scenarios - we'll return cards based on call order
        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )
        counterspell = Card(name="Counterspell", quantity_owned=4, quantity_available=4)

        call_count = [0]
        cards = [lightning_bolt, counterspell, None]  # None for Force of Will

        def mock_first():
            card = cards[call_count[0]] if call_count[0] < len(cards) else None
            call_count[0] += 1
            return card

        mock_session.scalars.return_value.first.side_effect = mock_first

        required_cards = {
            "Lightning Bolt": 3,  # Need 1 more (have 2 available)
            "Counterspell": 2,  # Have enough (have 4 available)
            "Force of Will": 1,  # Need all (don't have any)
        }

        result = service.calculate_needed_cards(required_cards)

        expected = {
            "Lightning Bolt": 1,  # 3 needed - 2 available = 1
            "Force of Will": 1,  # 1 needed - 0 available = 1
        }
        assert result == expected

    def test_check_allocation_feasibility(self, service, mock_sessionmaker):
        """Test checking allocation feasibility without actually allocating."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=2
        )

        call_count = [0]
        cards = [lightning_bolt, None]  # None for Nonexistent Card

        def mock_first():
            card = cards[call_count[0]] if call_count[0] < len(cards) else None
            call_count[0] += 1
            return card

        mock_session.scalars.return_value.first.side_effect = mock_first

        card_quantities = {
            "Lightning Bolt": 3,  # Need 1 more than available
            "Nonexistent Card": 2,  # Doesn't exist
        }

        result = service.check_allocation_feasibility(card_quantities)

        expected = {
            "Lightning Bolt": 1,  # 3 needed - 2 available = 1
            "Nonexistent Card": 2,  # 2 needed - 0 available = 2
        }
        assert result == expected

        # Original card should be unchanged
        assert lightning_bolt.quantity_available == 2

    def test_get_current_deck_allocation(self, service, mock_sessionmaker):
        """Test getting current allocation for a deck."""
        mock_session = Mock()
        mock_sessionmaker.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.return_value.__exit__ = Mock(return_value=None)

        mock_entries = [
            DeckEntry(decklist_id=1, card_name="Lightning Bolt", quantity=4),
            DeckEntry(decklist_id=1, card_name="Counterspell", quantity=2),
        ]
        mock_session.scalars.return_value.all.return_value = mock_entries

        result = service.get_current_deck_allocation(1)

        expected = {"Lightning Bolt": 4, "Counterspell": 2}
        assert result == expected

    def test_release_decklist_allocation(self, service, mock_sessionmaker):
        """Test releasing all cards allocated to a decklist."""
        mock_session = Mock()
        mock_sessionmaker.begin.return_value.__enter__ = Mock(return_value=mock_session)
        mock_sessionmaker.begin.return_value.__exit__ = Mock(return_value=None)

        # Mock deck entries
        mock_entries = [
            DeckEntry(decklist_id=1, card_name="Lightning Bolt", quantity=4),
            DeckEntry(decklist_id=1, card_name="Counterspell", quantity=2),
        ]

        # Mock cards
        lightning_bolt = Card(
            name="Lightning Bolt", quantity_owned=4, quantity_available=0
        )
        counterspell = Card(name="Counterspell", quantity_owned=2, quantity_available=0)

        # First call returns entries, subsequent calls return the cards
        call_count = [0]

        def mock_scalars_side_effect(query):
            mock_result = Mock()
            if call_count[0] == 0:
                # First call: get DeckEntry list
                mock_result.all.return_value = mock_entries
                call_count[0] += 1
            else:
                # Subsequent calls: get individual cards
                if call_count[0] == 1:
                    mock_result.first.return_value = lightning_bolt
                else:
                    mock_result.first.return_value = counterspell
                call_count[0] += 1
            return mock_result

        mock_session.scalars.side_effect = mock_scalars_side_effect

        service.release_decklist_allocation(1)

        # Cards should be released back to available
        assert lightning_bolt.quantity_available == 4
        assert counterspell.quantity_available == 2
