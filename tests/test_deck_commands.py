"""Tests for NetDecker deck commands."""

import argparse
from unittest.mock import Mock, patch

import pytest

from netdecker.cli.commands.deck import (
    deck_add,
    deck_batch,
    deck_delete,
    deck_list,
    deck_order,
    deck_show,
    deck_update,
    handle_command,
    setup_parser,
)
from netdecker.cli.result import CommandResult


class TestDeckSetupParser:
    """Test cases for deck command parser setup."""

    def test_setup_parser(self):
        """Test that deck parser is set up correctly."""
        mock_subparsers = Mock()
        mock_deck_parser = Mock()
        mock_deck_subparsers = Mock()

        mock_subparsers.add_parser.return_value = mock_deck_parser
        mock_deck_parser.add_subparsers.return_value = mock_deck_subparsers

        setup_parser(mock_subparsers)

        # Verify main deck parser was created
        mock_subparsers.add_parser.assert_called_once_with(
            "deck", help="Deck management commands"
        )

        # Verify subparsers were created
        mock_deck_parser.add_subparsers.assert_called_once_with(dest="deck_command")

        # Verify all expected subcommands were added
        expected_calls = ["list", "show", "add", "update", "delete", "batch", "order"]
        actual_calls = [
            call[0][0] for call in mock_deck_subparsers.add_parser.call_args_list
        ]

        for expected in expected_calls:
            assert expected in actual_calls


class TestDeckHandleCommand:
    """Test cases for deck command handling."""

    @pytest.mark.parametrize(
        "subcommand,handler_name",
        [
            ("list", "deck_list"),
            ("show", "deck_show"),
            ("add", "deck_add"),
            ("update", "deck_update"),
            ("delete", "deck_delete"),
            ("batch", "deck_batch"),
            ("order", "deck_order"),
        ],
    )
    def test_handle_command_valid(
        self, subcommand, handler_name, capture_exits, mock_workflow
    ):
        """Test handling of valid deck subcommands."""
        args = argparse.Namespace(deck_command=subcommand, name="Test Deck")

        with (
            patch(f"netdecker.cli.commands.deck.{handler_name}") as mock_handler,
            patch(
                "netdecker.cli.commands.deck.DeckManagementWorkflow",
                return_value=mock_workflow,
            ),
        ):
            mock_result = CommandResult(success=True, message="Success")
            mock_handler.return_value = mock_result

            handle_command(args)

            mock_handler.assert_called_once_with(args, mock_workflow)
            capture_exits.assert_not_called()

    def test_handle_command_unknown(self, capture_exits, mock_workflow):
        """Test handling of unknown deck subcommand."""
        args = argparse.Namespace(deck_command="unknown")

        with patch(
            "netdecker.cli.commands.deck.DeckManagementWorkflow",
            return_value=mock_workflow,
        ):
            handle_command(args)

            capture_exits.assert_called_once_with(1)


class TestDeckList:
    """Test cases for deck list command."""

    def test_deck_list_with_decks(self, mock_workflow, mock_logger):
        """Test listing decks when decks exist."""
        args = argparse.Namespace()

        result = deck_list(args, mock_workflow)

        assert result.success is True
        mock_workflow.decklists.list_decklists.assert_called_once()

        # Verify table headers were logged
        info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
        assert any("Format" in call and "Name" in call for call in info_calls)

    def test_deck_list_no_decks(self, mock_workflow):
        """Test listing decks when no decks exist."""
        mock_workflow.decklists.list_decklists.return_value = []
        args = argparse.Namespace()

        result = deck_list(args, mock_workflow)

        assert result.success is True
        assert "No tracked decks found" in result.message


class TestDeckShow:
    """Test cases for deck show command."""

    def test_deck_show_success(self, mock_workflow, mock_logger):
        """Test showing a deck that exists."""
        args = argparse.Namespace(name="Test Deck", format="Modern")

        with patch(
            "netdecker.cli.commands.deck.find_deck",
            return_value=mock_workflow.decklists.get_decklist.return_value,
        ):
            result = deck_show(args, mock_workflow)

            assert result.success is True
            mock_workflow.decklists.get_decklist_cards.assert_called_once()

            # Verify deck information was logged
            info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
            assert any("Deck:" in call for call in info_calls)
            assert any("URL:" in call for call in info_calls)

    def test_deck_show_not_found(self, mock_workflow):
        """Test showing a deck that doesn't exist."""
        args = argparse.Namespace(name="Nonexistent Deck", format="Modern")

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_show(args, mock_workflow)

            assert result.success is False
            assert "not found" in result.message


class TestDeckAdd:
    """Test cases for deck add command."""

    def test_deck_add_success(self, mock_workflow):
        """Test successfully adding a new deck."""
        args = argparse.Namespace(
            name="New Deck", url="https://example.com/deck", format="Modern"
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_add(args, mock_workflow)

            assert result.success is True
            assert "Added deck" in result.message
            mock_workflow.apply_deck_update.assert_called_once_with(
                args.url, args.format, args.name
            )

    def test_deck_add_already_exists(self, mock_workflow):
        """Test adding a deck that already exists."""
        args = argparse.Namespace(
            name="Existing Deck", url="https://example.com/deck", format="Modern"
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=Mock()):
            result = deck_add(args, mock_workflow)

            assert result.success is False
            assert "already exists" in result.message

    def test_deck_add_with_cards_to_order(self, mock_workflow):
        """Test adding a deck that requires ordering cards."""
        from netdecker.workflows.deck_management import DeckSwaps, DeckUpdatePreview

        swaps = DeckSwaps(cards_to_add={"Lightning Bolt": 4})
        preview_with_order = DeckUpdatePreview(
            deck_name="New Deck",
            deck_format="Modern",
            swaps=swaps,
            cards_to_order={"Lightning Bolt": 4},
            errors=[],
        )
        mock_workflow.apply_deck_update.return_value = preview_with_order

        args = argparse.Namespace(
            name="New Deck", url="https://example.com/deck", format="Modern"
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_add(args, mock_workflow)

            assert result.success is True
            assert "need to order" in result.message


class TestDeckUpdate:
    """Test cases for deck update command."""

    def test_deck_update_success(self, mock_workflow):
        """Test successfully updating an existing deck."""
        args = argparse.Namespace(
            name="Test Deck",
            url="https://example.com/new-deck",
            format="Modern",
            preview=False,
        )

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_update(args, mock_workflow)

            assert result.success is True
            mock_workflow.apply_deck_update.assert_called_once()

    def test_deck_update_preview(self, mock_workflow, mock_logger):
        """Test previewing deck update without applying."""
        args = argparse.Namespace(
            name="Test Deck",
            url=None,  # Use stored URL
            format="Modern",
            preview=True,
        )

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"
        mock_deck.url = "https://example.com/stored-url"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_update(args, mock_workflow)

            assert result.success is True
            mock_workflow.preview_deck_update.assert_called_once()

            # Verify preview message was logged
            info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
            assert any("This was a preview" in call for call in info_calls)

    def test_deck_update_not_found(self, mock_workflow):
        """Test updating a deck that doesn't exist."""
        args = argparse.Namespace(name="Nonexistent", format="Modern")

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_update(args, mock_workflow)

            assert result.success is False
            assert "not found" in result.message


class TestDeckDelete:
    """Test cases for deck delete command."""

    def test_deck_delete_confirmed(self, mock_workflow):
        """Test deleting a deck with confirmation."""
        args = argparse.Namespace(name="Test Deck", format="Modern", confirm=True)

        mock_deck = Mock()
        mock_deck.id = 1
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_delete(args, mock_workflow)

            assert result.success is True
            assert "Deleted deck" in result.message
            mock_workflow.allocation.release_decklist_allocation.assert_called_once_with(
                1
            )
            mock_workflow.decklists.delete_decklist.assert_called_once_with(1)

    def test_deck_delete_interactive_yes(self, mock_workflow):
        """Test deleting a deck with interactive confirmation (yes)."""
        args = argparse.Namespace(name="Test Deck", format="Modern", confirm=False)

        mock_deck = Mock()
        mock_deck.id = 1
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with (
            patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck),
            patch("builtins.input", return_value="y"),
        ):
            result = deck_delete(args, mock_workflow)

            assert result.success is True
            assert "Deleted deck" in result.message

    def test_deck_delete_interactive_no(self, mock_workflow):
        """Test canceling deck deletion with interactive confirmation."""
        args = argparse.Namespace(name="Test Deck", format="Modern", confirm=False)

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with (
            patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck),
            patch("builtins.input", return_value="n"),
        ):
            result = deck_delete(args, mock_workflow)

            assert result.success is True
            assert "Cancelled" in result.message


class TestDeckBatch:
    """Test cases for deck batch command."""

    def test_deck_batch_success(self, mock_workflow, temp_yaml_file):
        """Test successful batch processing of decks."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            preview=False,
            order_file=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.apply_batch_update.assert_called_once()

    def test_deck_batch_preview(self, mock_workflow, temp_yaml_file, mock_logger):
        """Test previewing batch processing without applying."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            preview=True,
            order_file=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.preview_batch_update.assert_called_once()

        # Verify preview message was logged
        info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
        assert any("This was a preview" in call for call in info_calls)

    def test_deck_batch_with_order_file(self, mock_workflow, temp_yaml_file, tmp_path):
        """Test batch processing with order file output."""
        order_file = tmp_path / "order.txt"

        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            preview=False,
            order_file=str(order_file),
            no_tokens=True,
        )

        # Mock result with order data by creating a preview with cards_to_order
        from netdecker.workflows.deck_management import (
            BatchUpdatePreview,
            DeckSwaps,
            DeckUpdatePreview,
        )

        swaps = DeckSwaps(cards_to_add={"Lightning Bolt": 4})
        preview_with_order = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            swaps=swaps,
            cards_to_order={"Lightning Bolt": 4},
            errors=[],
        )

        batch_preview_with_order = BatchUpdatePreview(deck_updates=[preview_with_order])
        mock_workflow.apply_batch_update.return_value = batch_preview_with_order

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.write_order_to_mpcfill.assert_called()

    def test_deck_batch_invalid_yaml(self, mock_workflow):
        """Test batch processing with invalid YAML file."""
        args = argparse.Namespace(
            yaml_file="/nonexistent/file.yaml",
            preview=False,
            order_file=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is False
        assert "Failed to load YAML file" in result.message


class TestDeckOrder:
    """Test cases for deck order command."""

    def test_deck_order_existing_deck(self, mock_workflow):
        """Test generating order for an existing deck."""
        args = argparse.Namespace(
            deck="Test Deck",
            url=None,
            yaml=None,
            format=None,
            output=None,
            no_tokens=False,
        )

        mock_deck = Mock()
        mock_deck.url = "https://example.com/deck"
        mock_deck.format = "Modern"
        mock_deck.name = "Test Deck"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_order(args, mock_workflow)

            assert result.success is True
            mock_workflow.preview_deck_update.assert_called_once_with(
                mock_deck.url, mock_deck.format, mock_deck.name
            )

    def test_deck_order_url(self, mock_workflow):
        """Test generating order for a URL."""
        args = argparse.Namespace(
            deck=None,
            url="https://example.com/deck",
            yaml=None,
            format="Modern",
            output=None,
            no_tokens=False,
        )

        result = deck_order(args, mock_workflow)

        assert result.success is True
        mock_workflow.preview_deck_update.assert_called_once_with(
            args.url, args.format, "temp-order"
        )

    def test_deck_order_url_no_format(self, mock_workflow):
        """Test generating order for URL without format (should fail)."""
        args = argparse.Namespace(
            deck=None,
            url="https://example.com/deck",
            yaml=None,
            format=None,
            output=None,
            no_tokens=False,
        )

        result = deck_order(args, mock_workflow)

        assert result.success is False
        assert "--format is required" in result.message

    def test_deck_order_yaml(self, mock_workflow, temp_yaml_file):
        """Test generating order for YAML file."""
        args = argparse.Namespace(
            deck=None,
            url=None,
            yaml=str(temp_yaml_file),
            format=None,
            output=None,
            no_tokens=False,
        )

        result = deck_order(args, mock_workflow)

        assert result.success is True
        mock_workflow.preview_batch_update.assert_called_once()

    def test_deck_order_with_output_file(self, mock_workflow, tmp_path):
        """Test generating order with output file."""
        output_file = tmp_path / "order.txt"

        args = argparse.Namespace(
            deck="Test Deck",
            url=None,
            yaml=None,
            format=None,
            output=str(output_file),
            no_tokens=True,
        )

        mock_deck = Mock()
        mock_deck.url = "https://example.com/deck"
        mock_deck.format = "Modern"
        mock_deck.name = "Test Deck"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_order(args, mock_workflow)

            assert result.success is True
            assert f"Order written to {output_file}" in result.message
