"""Tests for NetDecker workflow layer."""

from io import StringIO
from unittest.mock import Mock, patch

import pytest

from netdecker.models.decklist import Decklist
from netdecker.workflows.deck_management import (
    BatchUpdatePreview,
    DeckManagementWorkflow,
    DeckSwaps,
    DeckUpdatePreview,
)


class TestDeckSwaps:
    """Test cases for DeckSwaps dataclass."""

    def test_deck_swaps_default(self):
        """Test DeckSwaps with default values."""
        swaps = DeckSwaps()
        assert swaps.cards_to_add == {}
        assert swaps.cards_to_remove == {}
        assert swaps.has_changes is False

    def test_deck_swaps_with_changes(self):
        """Test DeckSwaps with actual changes."""
        swaps = DeckSwaps(
            cards_to_add={"Lightning Bolt": 4}, cards_to_remove={"Counterspell": 2}
        )
        assert swaps.has_changes is True

    @pytest.mark.parametrize(
        "add_cards,remove_cards,expected",
        [
            ({}, {}, False),
            ({"Lightning Bolt": 4}, {}, True),
            ({}, {"Counterspell": 2}, True),
            ({"Lightning Bolt": 4}, {"Counterspell": 2}, True),
        ],
    )
    def test_has_changes_property(self, add_cards, remove_cards, expected):
        """Test has_changes property with various combinations."""
        swaps = DeckSwaps(cards_to_add=add_cards, cards_to_remove=remove_cards)
        assert swaps.has_changes is expected


class TestDeckUpdatePreview:
    """Test cases for DeckUpdatePreview dataclass."""

    def test_deck_update_preview_default(self):
        """Test DeckUpdatePreview with defaults."""
        preview = DeckUpdatePreview(deck_name="Test Deck", deck_format="Modern")

        assert preview.deck_name == "Test Deck"
        assert preview.deck_format == "Modern"
        assert isinstance(preview.swaps, DeckSwaps)
        assert preview.cards_to_order == {}
        assert preview.errors == []
        assert preview.info_messages == []
        assert preview.total_cards_to_order == 0

    def test_total_cards_to_order(self):
        """Test total_cards_to_order calculation."""
        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            cards_to_order={"Lightning Bolt": 4, "Counterspell": 2},
        )
        assert preview.total_cards_to_order == 6

    def test_to_dict(self):
        """Test conversion to dictionary."""
        swaps = DeckSwaps(
            cards_to_add={"Lightning Bolt": 4}, cards_to_remove={"Counterspell": 2}
        )
        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            swaps=swaps,
            cards_to_order={"Force of Will": 1},
            errors=["Test error"],
            info_messages=["Test info"],
        )

        result = preview.to_dict()

        expected = {
            "deck_name": "Test Deck",
            "deck_format": "Modern",
            "swaps": {"add": {"Lightning Bolt": 4}, "remove": {"Counterspell": 2}},
            "cards_to_order": {"Force of Will": 1},
            "total_cards_to_order": 1,
            "errors": ["Test error"],
            "info_messages": ["Test info"],
        }
        assert result == expected


class TestBatchUpdatePreview:
    """Test cases for BatchUpdatePreview dataclass."""

    def test_batch_update_preview_default(self):
        """Test BatchUpdatePreview with defaults."""
        batch = BatchUpdatePreview()
        assert batch.deck_updates == []
        assert batch.total_order == {}
        assert batch.total_cards_to_order == 0

    def test_total_order_aggregation(self):
        """Test aggregation of cards to order across multiple decks."""
        preview1 = DeckUpdatePreview(
            deck_name="Deck 1",
            deck_format="Modern",
            cards_to_order={"Lightning Bolt": 4, "Counterspell": 2},
        )
        preview2 = DeckUpdatePreview(
            deck_name="Deck 2",
            deck_format="Legacy",
            cards_to_order={"Lightning Bolt": 2, "Force of Will": 1},
        )

        batch = BatchUpdatePreview(deck_updates=[preview1, preview2])

        expected_total = {
            "Lightning Bolt": 6,  # 4 + 2
            "Counterspell": 2,
            "Force of Will": 1,
        }
        assert batch.total_order == expected_total
        assert batch.total_cards_to_order == 9

    def test_to_dict(self):
        """Test conversion to dictionary."""
        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            cards_to_order={"Lightning Bolt": 4},
        )
        batch = BatchUpdatePreview(deck_updates=[preview])

        result = batch.to_dict()

        assert "deck_updates" in result
        assert "total_order" in result
        assert "total_cards_to_order" in result
        assert len(result["deck_updates"]) == 1
        assert result["total_cards_to_order"] == 4


class TestDeckManagementWorkflow:
    """Test cases for DeckManagementWorkflow."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        return {"inventory": Mock(), "allocation": Mock(), "decklists": Mock()}

    @pytest.fixture
    def workflow(self, mock_services):
        """Create DeckManagementWorkflow with mocked services."""
        return DeckManagementWorkflow(
            inventory_service=mock_services["inventory"],
            allocation_service=mock_services["allocation"],
            decklist_service=mock_services["decklists"],
        )

    def test_init(self, mock_services):
        """Test DeckManagementWorkflow initialization."""
        workflow = DeckManagementWorkflow(
            inventory_service=mock_services["inventory"],
            allocation_service=mock_services["allocation"],
            decklist_service=mock_services["decklists"],
        )

        assert workflow.inventory == mock_services["inventory"]
        assert workflow.allocation == mock_services["allocation"]
        assert workflow.decklists == mock_services["decklists"]

    @patch("netdecker.workflows.deck_management.fetch_decklist")
    def test_preview_deck_update_new_deck(self, mock_fetch, workflow, mock_services):
        """Test previewing update for a new deck."""
        # Mock fetch_decklist
        mock_fetch.return_value = {"Lightning Bolt": 4, "Counterspell": 2}

        # Mock deck doesn't exist
        mock_services["decklists"].get_decklist.return_value = None

        # Mock calculate_needed_cards
        mock_services["allocation"].calculate_needed_cards.return_value = {
            "Lightning Bolt": 2
        }

        result = workflow.preview_deck_update("http://test.com", "Modern", "New Deck")

        assert result.deck_name == "New Deck"
        assert result.deck_format == "Modern"
        assert result.swaps.cards_to_add == {"Lightning Bolt": 4, "Counterspell": 2}
        assert result.swaps.cards_to_remove == {}
        assert result.cards_to_order == {"Lightning Bolt": 2}
        assert result.errors == []

    @patch("netdecker.workflows.deck_management.fetch_decklist")
    def test_preview_deck_update_existing_deck(
        self, mock_fetch, workflow, mock_services
    ):
        """Test previewing update for an existing deck."""
        # Mock fetch_decklist
        mock_fetch.return_value = {"Lightning Bolt": 4, "Force of Will": 1}

        # Mock existing deck
        existing_deck = Decklist(id=1, name="Test Deck", format="Modern")
        mock_services["decklists"].get_decklist.return_value = existing_deck
        mock_services["decklists"].get_decklist_cards.return_value = {
            "Lightning Bolt": 2,
            "Counterspell": 2,
        }

        # Mock inventory methods
        mock_services["inventory"].get_available_quantity.side_effect = lambda card: {
            "Counterspell": 2
        }.get(card, 0)

        result = workflow.preview_deck_update("http://test.com", "Modern", "Test Deck")

        assert result.swaps.cards_to_add == {"Lightning Bolt": 2, "Force of Will": 1}
        assert result.swaps.cards_to_remove == {"Counterspell": 2}

    @patch("netdecker.workflows.deck_management.fetch_decklist")
    def test_preview_deck_update_with_error(self, mock_fetch, workflow):
        """Test preview when fetch_decklist raises an exception."""
        mock_fetch.side_effect = Exception("Network error")

        result = workflow.preview_deck_update("http://test.com", "Modern", "Test Deck")

        assert result.errors == ["Error processing deck: Network error"]

    @patch("netdecker.workflows.deck_management.fetch_decklist")
    def test_apply_deck_update_new_deck(self, mock_fetch, workflow, mock_services):
        """Test applying update for a new deck."""
        # Mock fetch_decklist
        mock_fetch.return_value = {"Lightning Bolt": 4, "Counterspell": 2}

        # Mock deck doesn't exist
        mock_services["decklists"].get_decklist.return_value = None
        mock_services["allocation"].calculate_needed_cards.return_value = {}

        # Mock deck creation
        mock_services["decklists"].create_decklist.return_value = 123
        mock_services["allocation"].allocate_cards.return_value = {}

        result = workflow.apply_deck_update("http://test.com", "Modern", "New Deck")

        # Verify deck was created and cards were allocated
        assert result.deck_name == "New Deck"
        assert result.deck_format == "Modern"
        mock_services["decklists"].create_decklist.assert_called_once_with(
            "New Deck", "Modern", "http://test.com"
        )
        mock_services["decklists"].update_decklist_cards.assert_called_once_with(
            123, {"Lightning Bolt": 4, "Counterspell": 2}
        )
        mock_services["allocation"].allocate_cards.assert_called_once()

    @patch("netdecker.workflows.deck_management.fetch_decklist")
    def test_apply_deck_update_existing_deck(self, mock_fetch, workflow, mock_services):
        """Test applying update for an existing deck."""
        # Mock fetch_decklist
        mock_fetch.return_value = {"Lightning Bolt": 4}

        # Mock existing deck
        existing_deck = Decklist(id=1, name="Test Deck", format="Modern")
        mock_services["decklists"].get_decklist.return_value = existing_deck
        mock_services["decklists"].get_decklist_cards.return_value = {"Counterspell": 2}
        mock_services["inventory"].get_available_quantity.return_value = 0
        mock_services["allocation"].allocate_cards.return_value = {}

        result = workflow.apply_deck_update("http://test.com", "Modern", "Test Deck")

        # Verify existing deck was updated
        assert result.deck_name == "Test Deck"
        assert result.deck_format == "Modern"
        mock_services["allocation"].release_decklist_allocation.assert_called_once_with(
            1
        )
        mock_services["decklists"].update_decklist_cards.assert_called_once_with(
            1, {"Lightning Bolt": 4}
        )
        mock_services["decklists"].update_decklist_url.assert_called_once_with(
            1, "http://test.com"
        )

    def test_preview_batch_update(self, workflow):
        """Test previewing batch update."""
        deck_configs = [
            {"url": "http://deck1.com", "format": "Modern", "name": "Deck 1"},
            {"url": "http://deck2.com", "format": "Legacy", "name": "Deck 2"},
        ]

        # Mock preview_deck_update
        with patch.object(workflow, "preview_deck_update") as mock_preview:
            mock_preview.side_effect = [
                DeckUpdatePreview(deck_name="Deck 1", deck_format="Modern"),
                DeckUpdatePreview(deck_name="Deck 2", deck_format="Legacy"),
            ]

            result = workflow.preview_batch_update(deck_configs)

            assert len(result.deck_updates) == 2
            assert mock_preview.call_count == 2

    def test_apply_batch_update(self, workflow):
        """Test applying batch update."""
        deck_configs = [
            {"url": "http://deck1.com", "format": "Modern", "name": "Deck 1"}
        ]

        # Mock apply_deck_update
        with patch.object(workflow, "apply_deck_update") as mock_apply:
            mock_apply.return_value = DeckUpdatePreview(
                deck_name="Deck 1", deck_format="Modern"
            )

            result = workflow.apply_batch_update(deck_configs)

            assert len(result.deck_updates) == 1
            mock_apply.assert_called_once()

    def test_write_preview_to_file_single(self, workflow):
        """Test writing single deck preview to file."""
        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            swaps=DeckSwaps(
                cards_to_add={"Lightning Bolt": 4}, cards_to_remove={"Counterspell": 2}
            ),
            cards_to_order={"Force of Will": 1},
            errors=["Test error"],
            info_messages=["Test info"],
        )

        output = StringIO()
        workflow.write_preview_to_file(preview, output)

        content = output.getvalue()
        assert "=== Deck Update Preview ===" in content
        assert "Test Deck (Modern)" in content
        assert "ERRORS:" in content
        assert "Test error" in content
        assert "INFO:" in content
        assert "Test info" in content
        assert "Cards to Remove:" in content
        assert "2x Counterspell" in content
        assert "Cards to Add:" in content
        assert "4x Lightning Bolt" in content
        assert "Cards to Order" in content
        assert "1x Force of Will" in content

    def test_write_preview_to_file_single_save_mode(self, workflow):
        """Test writing single deck preview to file in save mode."""
        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            swaps=DeckSwaps(
                cards_to_add={"Lightning Bolt": 4}, cards_to_remove={"Counterspell": 2}
            ),
            cards_to_order={"Force of Will": 1},
            info_messages=["Created 1 proxy cards for allocation"],
        )

        output = StringIO()
        workflow.write_preview_to_file(preview, output, save_mode=True)

        content = output.getvalue()
        assert "INFO:" in content
        assert "Created 1 proxy cards for allocation" in content
        assert "Updated deck 'Test Deck' (Modern) - 2 changes" in content
        assert "Need to order 1 cards" in content
        # Should not contain detailed card lists
        assert "Cards to Remove:" not in content
        assert "Cards to Add:" not in content

    def test_write_preview_to_file_batch(self, workflow):
        """Test writing batch preview to file."""
        preview1 = DeckUpdatePreview(
            deck_name="Deck 1",
            deck_format="Modern",
            swaps=DeckSwaps(cards_to_add={"Lightning Bolt": 4}),
        )
        preview2 = DeckUpdatePreview(
            deck_name="Deck 2",
            deck_format="Legacy",
            cards_to_order={"Force of Will": 1},
        )

        batch = BatchUpdatePreview(deck_updates=[preview1, preview2])

        output = StringIO()
        workflow.write_preview_to_file(batch, output)

        content = output.getvalue()
        assert "=== Batch Update Preview ===" in content
        assert "Total decks: 2" in content
        assert "Deck 1/2: Deck 1" in content
        assert "Deck 2/2: Deck 2" in content

    def test_write_preview_to_file_batch_save_mode(self, workflow):
        """Test writing batch preview to file in save mode."""
        preview1 = DeckUpdatePreview(
            deck_name="Deck 1",
            deck_format="Modern",
            swaps=DeckSwaps(cards_to_add={"Lightning Bolt": 4}),
        )
        preview2 = DeckUpdatePreview(
            deck_name="Deck 2",
            deck_format="Legacy",
            cards_to_order={"Force of Will": 1},
            errors=["Network error"],
        )

        batch = BatchUpdatePreview(deck_updates=[preview1, preview2])

        output = StringIO()
        workflow.write_preview_to_file(batch, output, save_mode=True)

        content = output.getvalue()
        assert "✓ Deck 1 (Modern) - 1 changes" in content
        assert "ERROR - Deck 2 (Legacy): Network error" in content
        assert "Summary: 1 successful, 1 errors" in content
        # Should not contain detailed batch preview format
        assert "=== Batch Update Preview ===" not in content

    @patch("netdecker.workflows.deck_management.get_card_tokens")
    def test_write_order_to_mpcfill_single(self, mock_get_tokens, workflow):
        """Test writing single deck order to MPCFill format."""
        mock_get_tokens.return_value = {"Beast Token": 1}

        preview = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            cards_to_order={"Lightning Bolt": 4, "Counterspell": 2},
        )

        output = StringIO()
        workflow.write_order_to_mpcfill(
            preview, output, include_tokens=True, fetch_tokens=True
        )

        content = output.getvalue()
        lines = content.strip().split("\n")

        # Check main cards
        assert "2 Counterspell" in lines
        assert "4 Lightning Bolt" in lines

        # Check tokens section
        assert "# Tokens" in content
        assert "1 Beast Token" in content

    @patch("netdecker.workflows.deck_management.get_card_tokens")
    def test_write_order_to_mpcfill_batch(self, mock_get_tokens, workflow):
        """Test writing batch order to MPCFill format."""
        mock_get_tokens.return_value = {}

        preview1 = DeckUpdatePreview(
            deck_name="Deck 1",
            deck_format="Modern",
            cards_to_order={"Lightning Bolt": 4},
        )
        preview2 = DeckUpdatePreview(
            deck_name="Deck 2",
            deck_format="Legacy",
            cards_to_order={"Lightning Bolt": 2, "Force of Will": 1},
        )

        batch = BatchUpdatePreview(deck_updates=[preview1, preview2])

        output = StringIO()
        workflow.write_order_to_mpcfill(
            batch, output, include_tokens=False, fetch_tokens=False
        )

        content = output.getvalue()
        lines = content.strip().split("\n")

        # Should aggregate: Lightning Bolt = 4+2=6, Force of Will = 1
        assert "1 Force of Will" in lines
        assert "6 Lightning Bolt" in lines

    def test_write_cube_csv(self, workflow, mock_services):
        """Test writing cube CSV format."""
        mock_services["decklists"].get_decklist_cards.return_value = {
            "Lightning Bolt": 2,
            "Counterspell": 1,
        }

        output = StringIO()
        workflow.write_cube_csv(1, output)

        content = output.getvalue()
        lines = content.strip().split("\n")

        # Should have header + 3 card entries (2 Lightning Bolt + 1 Counterspell)
        assert len(lines) == 4
        assert lines[0].startswith('"name"')  # Header
        assert '"Lightning Bolt"' in content
        assert '"Counterspell"' in content

    def test_calculate_swaps(self, workflow):
        """Test calculating swaps between two card lists."""
        current_cards = {"Lightning Bolt": 4, "Counterspell": 2, "Force of Will": 1}
        new_cards = {"Lightning Bolt": 2, "Brainstorm": 4, "Force of Will": 1}

        swaps = workflow._calculate_swaps(current_cards, new_cards)

        # Should add 4 Brainstorm, remove 2 Lightning Bolt and 2 Counterspell
        assert swaps.cards_to_add == {"Brainstorm": 4}
        assert swaps.cards_to_remove == {"Lightning Bolt": 2, "Counterspell": 2}

    def test_calculate_swaps_case_insensitive(self, workflow):
        """Test that swaps calculation is case insensitive."""
        current_cards = {"lightning bolt": 4}
        new_cards = {"Lightning Bolt": 2}

        swaps = workflow._calculate_swaps(current_cards, new_cards)

        # Should detect as same card, remove 2
        assert swaps.cards_to_add == {}
        assert swaps.cards_to_remove == {"lightning bolt": 2}

    def test_simulate_release(self, workflow, mock_services):
        """Test simulating card release."""
        mock_services["inventory"].get_available_quantity.side_effect = lambda card: {
            "Lightning Bolt": 2,
            "Counterspell": 1,
        }.get(card, 0)

        cards_to_remove = {"Lightning Bolt": 2, "Counterspell": 1}

        result = workflow._simulate_release(cards_to_remove)

        expected = {"Lightning Bolt": 4, "Counterspell": 2}  # current + released
        assert result == expected

    def test_calculate_order_needs(self, workflow, mock_services):
        """Test calculating what needs to be ordered."""
        mock_services["inventory"].get_available_quantity.side_effect = lambda card: {
            "Lightning Bolt": 1,
            "Counterspell": 0,
        }.get(card, 0)

        cards_to_add = {"Lightning Bolt": 4, "Counterspell": 2}
        simulated_available = {"Lightning Bolt": 2}  # Would have 2 after release

        result = workflow._calculate_order_needs(cards_to_add, simulated_available)

        expected = {
            "Lightning Bolt": 2,  # Need 4, would have 2 available = 2 to order
            "Counterspell": 2,  # Need 2, have 0 available = 2 to order
        }
        assert result == expected
