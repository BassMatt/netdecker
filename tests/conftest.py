"""Pytest configuration and shared fixtures for NetDecker CLI tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from netdecker.config import LOGGER
from netdecker.models.decklist import Decklist
from netdecker.workflows.deck_management import DeckManagementWorkflow


@pytest.fixture
def mock_db():
    """Mock database initialization."""
    with patch("netdecker.db.initialize_database", return_value=True):
        yield


@pytest.fixture
def mock_logger():
    """Mock logger to capture log messages."""
    with (
        patch.object(LOGGER, "info") as mock_info,
        patch.object(LOGGER, "error") as mock_error,
        patch.object(LOGGER, "warning") as mock_warning,
    ):
        yield {
            "info": mock_info,
            "error": mock_error,
            "warning": mock_warning,
        }


@pytest.fixture
def temp_yaml_file():
    """Create a temporary YAML file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml_content = {
            "decklists": [
                {
                    "format": "Modern",
                    "decks": [
                        {"name": "Test Deck 1", "url": "https://example.com/deck1"},
                        {"name": "Test Deck 2", "url": "https://example.com/deck2"},
                    ],
                },
                {
                    "format": "Vintage",
                    "decks": [
                        {"name": "Test Deck 3", "url": "https://example.com/deck3"}
                    ],
                },
            ]
        }
        import yaml

        yaml.dump(yaml_content, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_workflow():
    """Mock DeckManagementWorkflow for testing."""
    workflow = Mock(spec=DeckManagementWorkflow)

    # Mock decklists service
    workflow.decklists = Mock()
    workflow.allocation = Mock()

    # Mock deck data with proper datetime
    sample_deck = Decklist(
        id=1,
        name="Test Deck",
        format="Modern",
        url="https://example.com/deck",
        updated_at=datetime(2023, 1, 1, 12, 0, 0),
    )

    workflow.decklists.get_decklist.return_value = sample_deck
    workflow.decklists.get_decklist_by_name.return_value = sample_deck
    workflow.decklists.list_decklists.return_value = [sample_deck]
    workflow.decklists.get_decklist_cards.return_value = {
        "Lightning Bolt": 4,
        "Counterspell": 2,
    }
    workflow.decklists.delete_decklist.return_value = True

    # Mock preview results with correct structure
    from netdecker.workflows.deck_management import (
        BatchUpdatePreview,
        DeckSwaps,
        DeckUpdatePreview,
    )

    swaps = DeckSwaps(
        cards_to_add={"Lightning Bolt": 2}, cards_to_remove={"Counterspell": 1}
    )

    preview = DeckUpdatePreview(
        deck_name="Test Deck",
        deck_format="Modern",
        swaps=swaps,
        cards_to_order={},
        errors=[],
    )
    workflow.preview_deck_update.return_value = preview
    workflow.apply_deck_update.return_value = preview

    batch_preview = BatchUpdatePreview(deck_updates=[preview])
    workflow.preview_batch_update.return_value = batch_preview
    workflow.apply_batch_update.return_value = batch_preview

    # Mock file writing methods
    workflow.write_preview_to_file = Mock()
    workflow.write_order_to_mpcfill = Mock()

    return workflow


@pytest.fixture
def mock_card_inventory_service():
    """Mock card inventory service for proxy command testing."""
    with patch("netdecker.services.card_inventory_service") as mock_service:
        from netdecker.models.card import Card

        # Mock card data
        mock_cards = [
            Card(name="Lightning Bolt", quantity_owned=4, quantity_available=2),
            Card(name="Counterspell", quantity_owned=2, quantity_available=1),
        ]

        mock_service.list_all_cards.return_value = mock_cards
        mock_service.add_cards.return_value = None
        mock_service.remove_cards.return_value = None

        yield mock_service


@pytest.fixture
def mock_parse_cardlist():
    """Mock parse_cardlist utility function."""
    with patch("netdecker.utils.parse_cardlist") as mock_parse:
        mock_parse.return_value = {"Lightning Bolt": 4, "Counterspell": 2}
        yield mock_parse


@pytest.fixture(autouse=True)
def capture_exits():
    """Capture system exits to prevent tests from actually exiting."""
    with patch("builtins.exit") as mock_exit, patch("sys.exit"):
        yield mock_exit
