"""Tests for NetDecker deck commands."""

import argparse
from unittest.mock import Mock, patch

import pytest

from netdecker.cli.commands.deck import (
    deck_batch,
    deck_delete,
    deck_list,
    deck_show,
    deck_sync,
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
        expected_calls = ["list", "show", "sync", "delete", "batch"]
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
            ("sync", "deck_sync"),
            ("delete", "deck_delete"),
            ("batch", "deck_batch"),
        ],
    )
    def test_handle_command_valid(
        self, subcommand, handler_name, capture_exits, mock_workflow
    ):
        """Test handling of valid deck subcommands."""
        # Set up args with required attributes for validation
        args = argparse.Namespace(deck_command=subcommand, name="Test Deck")

        # Add required attributes for commands that need validation
        if subcommand in ["sync"]:
            # Sync command only has --save (default to preview mode)
            args.save = True
            args.output = "/tmp"  # Use a path that exists
            args.no_tokens = False
        elif subcommand == "batch":
            # Batch command only has --save (default to preview mode)
            args.save = True
            args.output = "/tmp"  # Use a path that exists
            args.no_tokens = False
            args.yaml_file = "test.yaml"
        elif subcommand == "delete":
            # Delete command has --confirm
            args.confirm = True

        with (
            patch(f"netdecker.cli.commands.deck.{handler_name}") as mock_handler,
            patch(
                "netdecker.cli.commands.deck.DeckManagementWorkflow",
                return_value=mock_workflow,
            ),
            patch("pathlib.Path.exists", return_value=True),  # Mock path exists
            patch("pathlib.Path.is_dir", return_value=True),  # Mock path is directory
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


class TestDeckSync:
    """Test cases for deck sync command."""

    def test_deck_sync_success(self, mock_workflow):
        """Test successfully syncing a deck."""
        args = argparse.Namespace(
            name="Test Deck",
            url="https://example.com/new-deck",
            format="Modern",
            save=True,
            preview=False,
            output=None,
            no_tokens=False,
        )

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            mock_workflow.apply_deck_update.assert_called_once()

    def test_deck_sync_preview(self, mock_workflow, mock_logger):
        """Test previewing deck sync without applying."""
        args = argparse.Namespace(
            name="Test Deck",
            url="https://example.com/deck",
            format="Modern",
            save=False,
            output=None,
            no_tokens=False,
        )

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"
        mock_deck.url = "https://example.com/stored-url"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            mock_workflow.preview_deck_update.assert_called_once()

            # Verify preview message was logged
            info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
            assert any("This was a preview" in call for call in info_calls)

    def test_deck_sync_not_found(self, mock_workflow):
        """Test syncing a deck that doesn't exist without format."""
        args = argparse.Namespace(
            name="Nonexistent",
            format=None,  # No format provided
            url="https://example.com/deck",
            save=True,
            output=None,
            no_tokens=False,
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_sync(args, mock_workflow)

            assert result.success is False
            assert "--format is required when adding a new deck" in result.message

    def test_deck_sync_with_save_flag(self, mock_workflow, tmp_path):
        """Test syncing a deck with --save flag to generate output files."""
        from netdecker.workflows.deck_management import DeckSwaps, DeckUpdatePreview

        swaps = DeckSwaps(cards_to_add={"Force of Will": 2})
        preview_with_order = DeckUpdatePreview(
            deck_name="Test Deck",
            deck_format="Modern",
            swaps=swaps,
            cards_to_order={"Force of Will": 2},
            errors=[],
            info_messages=[],
        )
        mock_workflow.apply_deck_update.return_value = preview_with_order

        args = argparse.Namespace(
            name="Test Deck",
            url="https://example.com/new-deck",
            format="Modern",
            save=True,
            output=str(tmp_path),
            no_tokens=True,
        )

        mock_deck = Mock()
        mock_deck.name = "Test Deck"
        mock_deck.format = "Modern"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            mock_workflow.apply_deck_update.assert_called_once()

            # Check that a dated directory was created
            created_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
            assert len(created_dirs) == 1
            deck_dir = created_dirs[0]
            assert deck_dir.name.startswith("modern-Test_Deck-")

            # Check that files were created in the deck directory
            assert (deck_dir / "swaps.txt").exists()
            assert (deck_dir / "order.txt").exists()

    def test_deck_sync_cube_with_save_flag(self, mock_workflow, tmp_path):
        """Test syncing a cube deck with --save flag to generate cube CSV."""
        from netdecker.workflows.deck_management import DeckUpdatePreview

        preview = DeckUpdatePreview(
            deck_name="My Cube",
            deck_format="Cube",
            errors=[],
            info_messages=[],
        )
        mock_workflow.apply_deck_update.return_value = preview

        mock_deck = Mock()
        mock_deck.id = 1
        mock_deck.name = "My Cube"
        mock_deck.format = "Cube"

        args = argparse.Namespace(
            name="My Cube",
            url="https://cubecobra.com/cube/overview/mycube",
            format="Cube",
            save=True,
            output=str(tmp_path),
            no_tokens=False,
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            mock_workflow.write_cube_csv.assert_called_once()

            # Check that a dated directory was created
            created_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
            assert len(created_dirs) == 1
            deck_dir = created_dirs[0]
            assert deck_dir.name.startswith("cube-My_Cube-")

            # Check that cube CSV was created in the deck directory
            assert (deck_dir / "cube.csv").exists()

    def test_deck_sync_add_new_deck_preview(self, mock_workflow):
        """Test syncing a new deck in preview mode."""
        args = argparse.Namespace(
            name="New Deck",
            url="https://example.com/deck",
            format="Modern",
            save=False,  # Default preview mode
            output=None,
            no_tokens=False,
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            mock_workflow.preview_deck_update.assert_called_once_with(
                args.url, args.format, args.name
            )
            mock_workflow.apply_deck_update.assert_not_called()

    def test_deck_sync_add_new_deck_save(self, mock_workflow, tmp_path):
        """Test syncing a new deck with --save flag."""
        from netdecker.workflows.deck_management import DeckSwaps, DeckUpdatePreview

        swaps = DeckSwaps(cards_to_add={"Lightning Bolt": 4})
        preview_with_order = DeckUpdatePreview(
            deck_name="New Deck",
            deck_format="Modern",
            swaps=swaps,
            cards_to_order={"Lightning Bolt": 4},
            errors=[],
            info_messages=[],
        )
        mock_workflow.apply_deck_update.return_value = preview_with_order

        args = argparse.Namespace(
            name="New Deck",
            url="https://example.com/deck",
            format="Modern",
            save=True,
            output=str(tmp_path),
            no_tokens=False,
        )

        mock_deck = Mock()
        mock_deck.id = 1

        with patch("netdecker.cli.commands.deck.find_deck") as mock_find:
            mock_find.side_effect = [
                None,
                mock_deck,
            ]  # First None (new), then deck after creation
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            assert "Added deck" in result.message
            mock_workflow.apply_deck_update.assert_called_once()

    def test_deck_sync_update_existing_deck(self, mock_workflow):
        """Test syncing an existing deck."""
        args = argparse.Namespace(
            name="Existing Deck",
            url="https://example.com/new-url",
            format=None,  # Should use existing deck's format
            save=True,
            output=None,
            no_tokens=False,
        )

        mock_deck = Mock()
        mock_deck.name = "Existing Deck"
        mock_deck.format = "Modern"

        with patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck):
            result = deck_sync(args, mock_workflow)

            assert result.success is True
            assert "Updated deck" in result.message
            mock_workflow.apply_deck_update.assert_called_once_with(
                args.url, mock_deck.format, mock_deck.name
            )

    def test_deck_sync_new_deck_no_format_error(self, mock_workflow):
        """Test syncing a new deck without format fails."""
        args = argparse.Namespace(
            name="New Deck",
            url="https://example.com/deck",
            format=None,  # Missing format for new deck
            save=False,
            output=None,
            no_tokens=False,
        )

        with patch("netdecker.cli.commands.deck.find_deck", return_value=None):
            result = deck_sync(args, mock_workflow)

            assert result.success is False
            assert "--format is required when adding a new deck" in result.message


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

        # Mock deck cards
        mock_deck_cards = {"Lightning Bolt": 4, "Counterspell": 2}
        mock_workflow.decklists.get_decklist_cards.return_value = mock_deck_cards

        # Create inventory mock
        mock_workflow.inventory = Mock()
        mock_card = Mock()
        mock_card.quantity_owned = 1
        mock_workflow.inventory.get_card.return_value = mock_card
        mock_workflow.inventory.remove_cards.return_value = None

        with (
            patch("netdecker.cli.commands.deck.find_deck", return_value=mock_deck),
            patch(
                "builtins.input", side_effect=["y", "n"]
            ),  # Delete deck: yes, Remove proxy cards: no
        ):
            result = deck_delete(args, mock_workflow)

        assert result.exit_code == 0
        mock_workflow.decklists.delete_decklist.assert_called_once_with(1)
        mock_workflow.allocation.release_decklist_allocation.assert_called_once_with(1)
        # Ensure we didn't remove proxy cards since user said no
        mock_workflow.inventory.remove_cards.assert_not_called()

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
        """Test successful batch processing of decks (default preview mode)."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            save=False,  # Default preview mode
            output=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.preview_batch_update.assert_called_once()
        mock_workflow.apply_batch_update.assert_not_called()

    def test_deck_batch_preview(self, mock_workflow, temp_yaml_file, mock_logger):
        """Test batch processing in default preview mode."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            save=False,  # Default preview mode
            output=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.preview_batch_update.assert_called_once()

        # Verify preview message was logged
        info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
        assert any("This was a preview" in call for call in info_calls)

    def test_deck_batch_with_save_flag(self, mock_workflow, temp_yaml_file, tmp_path):
        """Test batch processing with --save flag to persist changes."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            save=True,
            output=str(tmp_path),
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
            info_messages=[],
        )

        batch_preview_with_order = BatchUpdatePreview(deck_updates=[preview_with_order])
        mock_workflow.apply_batch_update.return_value = batch_preview_with_order

        result = deck_batch(args, mock_workflow)

        assert result.success is True
        mock_workflow.apply_batch_update.assert_called_once()
        mock_workflow.preview_batch_update.assert_not_called()

        # Check that a batch directory was created
        created_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(created_dirs) == 1
        batch_dir = created_dirs[0]
        assert batch_dir.name.startswith("batch-")

        # Check that batch order file was created
        assert (batch_dir / "batch_order.txt").exists()

        # Check that individual deck subdirectories were created
        deck_subdirs = [d for d in batch_dir.iterdir() if d.is_dir()]
        assert len(deck_subdirs) == 1
        deck_subdir = deck_subdirs[0]
        assert deck_subdir.name == "modern-Test_Deck"
        assert (deck_subdir / "swaps.txt").exists()

    def test_deck_batch_invalid_yaml(self, mock_workflow):
        """Test batch processing with invalid YAML file."""
        args = argparse.Namespace(
            yaml_file="/nonexistent/file.yaml",
            save=False,  # Default preview mode
            output=None,
            no_tokens=False,
        )

        result = deck_batch(args, mock_workflow)

        assert result.success is False
        assert "Failed to load YAML file" in result.message

    def test_deck_batch_with_cube_decks(self, mock_workflow, temp_yaml_file, tmp_path):
        """Test batch processing with --save flag for cube decks."""
        args = argparse.Namespace(
            yaml_file=str(temp_yaml_file),
            save=True,
            output=str(tmp_path),
            no_tokens=False,
        )

        # Mock cube deck in config
        mock_cube_deck = Mock()
        mock_cube_deck.id = 1
        mock_cube_deck.name = "My Cube"
        mock_cube_deck.format = "Cube"

        # Mock the extract_deck_configs to return cube deck
        with patch("netdecker.cli.commands.deck.extract_deck_configs") as mock_extract:
            mock_extract.return_value = [
                {"name": "My Cube", "format": "Cube", "url": "https://example.com"}
            ]

            with patch(
                "netdecker.cli.commands.deck.find_deck", return_value=mock_cube_deck
            ):
                result = deck_batch(args, mock_workflow)

                assert result.success is True
                mock_workflow.write_cube_csv.assert_called_once()

                # Check that a batch directory was created
                created_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
                assert len(created_dirs) == 1
                batch_dir = created_dirs[0]
                assert batch_dir.name.startswith("batch-")

                # Check that cube CSV was created in the batch directory
                assert (batch_dir / "cubes.csv").exists()


class TestDeckValidation:
    """Test cases for deck command validation."""

    def test_validate_output_args_save_requires_output_sync(self):
        """Test that --save requires --output for sync command."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="sync",
            save=True,
            output=None,
        )

        result = _validate_output_args(args)
        assert result == "--output directory is required when using --save"

    def test_validate_output_args_save_requires_output_batch(self):
        """Test that --save requires --output for batch command."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="batch",
            save=True,
            output=None,
        )

        result = _validate_output_args(args)
        assert result == "--output directory is required when using --save"

    def test_validate_output_args_sync_default_preview_no_output_required(self):
        """Test that sync command in default preview mode doesn't require --output."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="sync",
            save=False,
            output=None,
        )

        result = _validate_output_args(args)
        assert result is None

    def test_validate_output_args_batch_default_preview_no_output_required(self):
        """Test that batch command in default preview mode doesn't require --output."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="batch",
            save=False,
            output=None,
        )

        result = _validate_output_args(args)
        assert result is None

    def test_validate_output_args_nonexistent_directory(self):
        """Test validation fails for nonexistent output directory."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="sync",
            save=True,
            output="/nonexistent/directory",
        )

        result = _validate_output_args(args)
        assert result == "Output directory '/nonexistent/directory' does not exist"

    def test_validate_output_args_file_not_directory(self, tmp_path):
        """Test validation fails when output path is a file, not directory."""
        from netdecker.cli.commands.deck import _validate_output_args

        # Create a file instead of directory
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test")

        args = argparse.Namespace(
            deck_command="sync",
            save=True,
            output=str(test_file),
        )

        result = _validate_output_args(args)
        assert "is not a directory" in result

    def test_validate_output_args_valid_directory(self, tmp_path):
        """Test validation passes for valid directory."""
        from netdecker.cli.commands.deck import _validate_output_args

        args = argparse.Namespace(
            deck_command="sync",
            save=True,
            output=str(tmp_path),
        )

        result = _validate_output_args(args)
        assert result is None
