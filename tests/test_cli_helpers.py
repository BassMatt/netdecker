"""Tests for NetDecker CLI helper functions."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from netdecker.cli.helpers import extract_deck_configs, find_deck, load_yaml_config


class TestFindDeck:
    """Test cases for find_deck helper function."""

    def test_find_deck_with_format(self, mock_workflow):
        """Test finding a deck with specified format."""
        mock_deck = Mock()
        mock_workflow.decklists.get_decklist.return_value = mock_deck

        result = find_deck("Test Deck", "Modern", mock_workflow)

        assert result == mock_deck
        mock_workflow.decklists.get_decklist.assert_called_once_with(
            "Test Deck", "Modern"
        )

    def test_find_deck_without_format(self, mock_workflow):
        """Test finding a deck without specified format."""
        mock_deck = Mock()
        mock_workflow.decklists.get_decklist_by_name.return_value = mock_deck

        result = find_deck("Test Deck", None, mock_workflow)

        assert result == mock_deck
        mock_workflow.decklists.get_decklist_by_name.assert_called_once_with(
            "Test Deck"
        )

    def test_find_deck_not_found_with_logging(self, mock_workflow, mock_logger):
        """Test finding a deck that doesn't exist with error logging."""
        mock_workflow.decklists.get_decklist.return_value = None

        result = find_deck("Nonexistent", "Modern", mock_workflow, log_error=True)

        assert result is None
        mock_logger["error"].assert_called_once()

    def test_find_deck_not_found_without_logging(self, mock_workflow, mock_logger):
        """Test finding a deck that doesn't exist without error logging."""
        mock_workflow.decklists.get_decklist.return_value = None

        result = find_deck("Nonexistent", "Modern", mock_workflow, log_error=False)

        assert result is None
        mock_logger["error"].assert_not_called()


class TestLoadYamlConfig:
    """Test cases for load_yaml_config helper function."""

    def test_load_yaml_config_success(self):
        """Test successfully loading a YAML config file."""
        config_data = {
            "decklists": [
                {
                    "format": "Modern",
                    "decks": [{"name": "Test Deck", "url": "https://example.com/deck"}],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            result = load_yaml_config(str(temp_path))
            assert result == config_data
        finally:
            temp_path.unlink()

    def test_load_yaml_config_file_not_found(self):
        """Test loading a YAML config file that doesn't exist."""
        result = load_yaml_config("/nonexistent/file.yaml")

        assert result is None

    def test_load_yaml_config_invalid_yaml(self):
        """Test loading an invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = Path(f.name)

        try:
            with pytest.raises(yaml.YAMLError):
                load_yaml_config(str(temp_path))
        finally:
            temp_path.unlink()


class TestExtractDeckConfigs:
    """Test cases for extract_deck_configs helper function."""

    def test_extract_deck_configs_success(self):
        """Test successfully extracting deck configurations from YAML."""
        config = {
            "decklists": [
                {
                    "format": "Modern",
                    "decks": [
                        {"name": "Deck 1", "url": "https://example.com/deck1"},
                        {"name": "Deck 2", "url": "https://example.com/deck2"},
                    ],
                },
                {
                    "format": "Vintage",
                    "decks": [{"name": "Deck 3", "url": "https://example.com/deck3"}],
                },
            ]
        }

        result = extract_deck_configs(config)

        expected = [
            {"name": "Deck 1", "format": "Modern", "url": "https://example.com/deck1"},
            {"name": "Deck 2", "format": "Modern", "url": "https://example.com/deck2"},
            {"name": "Deck 3", "format": "Vintage", "url": "https://example.com/deck3"},
        ]

        assert result == expected

    def test_extract_deck_configs_empty(self):
        """Test extracting from empty configuration."""
        config = {}

        result = extract_deck_configs(config)

        assert result == []

    def test_extract_deck_configs_no_decklists(self):
        """Test extracting from config without decklists key."""
        config = {"other_key": "value"}

        result = extract_deck_configs(config)

        assert result == []

    def test_extract_deck_configs_empty_decks(self):
        """Test extracting from config with empty decks."""
        config = {"decklists": [{"format": "Modern", "decks": []}]}

        result = extract_deck_configs(config)

        assert result == []

    def test_extract_deck_configs_missing_format(self):
        """Test extracting from config with missing format."""
        config = {
            "decklists": [
                {"decks": [{"name": "Deck 1", "url": "https://example.com/deck1"}]}
            ]
        }

        result = extract_deck_configs(config)

        expected = [
            {"name": "Deck 1", "format": "Unknown", "url": "https://example.com/deck1"}
        ]

        assert result == expected

    def test_extract_deck_configs_missing_decks(self):
        """Test extracting from config with missing decks key."""
        config = {"decklists": [{"format": "Modern"}]}

        result = extract_deck_configs(config)

        assert result == []

    @pytest.mark.parametrize(
        "config_data,expected_count",
        [
            ({"decklists": []}, 0),
            (
                {
                    "decklists": [
                        {"format": "Modern", "decks": [{"name": "D1", "url": "U1"}]}
                    ]
                },
                1,
            ),
            (
                {
                    "decklists": [
                        {
                            "format": "Modern",
                            "decks": [
                                {"name": "D1", "url": "U1"},
                                {"name": "D2", "url": "U2"},
                            ],
                        },
                        {"format": "Legacy", "decks": [{"name": "D3", "url": "U3"}]},
                    ]
                },
                3,
            ),
        ],
    )
    def test_extract_deck_configs_parametrized(self, config_data, expected_count):
        """Test extracting deck configs with various input sizes."""
        result = extract_deck_configs(config_data)

        assert len(result) == expected_count

        # Verify all entries have required keys
        for deck_config in result:
            assert "name" in deck_config
            assert "format" in deck_config
            assert "url" in deck_config
