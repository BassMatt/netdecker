"""Tests for NetDecker proxy commands."""

import argparse
from unittest.mock import Mock, patch

import pytest

from netdecker.cli.commands.proxy import (
    handle_command,
    proxy_add,
    proxy_list,
    proxy_remove,
    setup_parser,
)
from netdecker.cli.result import CommandResult


class TestProxySetupParser:
    """Test cases for proxy command parser setup."""

    def test_setup_parser(self):
        """Test that proxy parser is set up correctly."""
        mock_subparsers = Mock()
        mock_proxy_parser = Mock()
        mock_proxy_subparsers = Mock()

        mock_subparsers.add_parser.return_value = mock_proxy_parser
        mock_proxy_parser.add_subparsers.return_value = mock_proxy_subparsers

        setup_parser(mock_subparsers)

        # Verify main proxy parser was created
        mock_subparsers.add_parser.assert_called_once_with(
            "proxy", help="Commands to manage proxy cards"
        )

        # Verify subparsers were created
        mock_proxy_parser.add_subparsers.assert_called_once_with(dest="proxy_command")

        # Verify subcommands were added
        expected_calls = ["add", "list", "remove"]
        actual_calls = [
            call[0][0] for call in mock_proxy_subparsers.add_parser.call_args_list
        ]

        for expected in expected_calls:
            assert expected in actual_calls


class TestProxyHandleCommand:
    """Test cases for proxy command handling."""

    @pytest.mark.parametrize(
        "subcommand,handler_name",
        [
            ("add", "proxy_add"),
            ("list", "proxy_list"),
            ("remove", "proxy_remove"),
        ],
    )
    def test_handle_command_valid(self, subcommand, handler_name, capture_exits):
        """Test handling of valid proxy subcommands."""
        args = argparse.Namespace(
            proxy_command=subcommand, card_entries=["4 Lightning Bolt"]
        )

        with patch(f"netdecker.cli.commands.proxy.{handler_name}") as mock_handler:
            mock_result = CommandResult(success=True, message="Success")
            mock_handler.return_value = mock_result

            handle_command(args)

            mock_handler.assert_called_once_with(args)
            capture_exits.assert_not_called()

    def test_handle_command_with_error(self, capture_exits):
        """Test handling when command returns error."""
        args = argparse.Namespace(
            proxy_command="add", card_entries=["4 Lightning Bolt"]
        )

        with patch("netdecker.cli.commands.proxy.proxy_add") as mock_handler:
            mock_result = CommandResult(success=False, message="Error occurred")
            mock_handler.return_value = mock_result

            handle_command(args)

            capture_exits.assert_called_once_with(mock_result.exit_code)

    def test_handle_command_unknown(self, capture_exits):
        """Test handling of unknown proxy subcommand."""
        args = argparse.Namespace(proxy_command="unknown")

        handle_command(args)

        capture_exits.assert_called_once_with(1)


class TestProxyAdd:
    """Test cases for proxy add command."""

    def test_proxy_add_success(self):
        """Test successful proxy card addition."""
        args = argparse.Namespace(card_entries=["4 Lightning Bolt", "2 Counterspell"])

        with (
            patch("netdecker.cli.commands.proxy.parse_cardlist") as mock_parse,
            patch(
                "netdecker.cli.commands.proxy.card_inventory_service"
            ) as mock_service,
        ):
            mock_parse.return_value = {"Lightning Bolt": 4, "Counterspell": 2}

            result = proxy_add(args)

            assert result.success is True
            assert "Added 6 cards to inventory" in result.message
            mock_parse.assert_called_once_with(args.card_entries)
            mock_service.add_cards.assert_called_once_with(
                {"Lightning Bolt": 4, "Counterspell": 2}
            )

    def test_proxy_add_empty_cards(self):
        """Test proxy add with empty card list."""
        args = argparse.Namespace(card_entries=[])

        with (
            patch("netdecker.cli.commands.proxy.parse_cardlist", return_value={}),
            patch(
                "netdecker.cli.commands.proxy.card_inventory_service"
            ) as _mock_service,
        ):
            result = proxy_add(args)

            assert result.success is True
            assert "Added 0 cards to inventory" in result.message


class TestProxyList:
    """Test cases for proxy list command."""

    def test_proxy_list_with_cards(self, mock_logger):
        """Test listing proxy cards when cards exist."""
        args = argparse.Namespace()

        with patch(
            "netdecker.cli.commands.proxy.card_inventory_service"
        ) as mock_service:
            from netdecker.models.card import Card

            mock_cards = [
                Card(name="Lightning Bolt", quantity_owned=4, quantity_available=2),
                Card(name="Counterspell", quantity_owned=2, quantity_available=1),
            ]
            mock_service.list_all_cards.return_value = mock_cards

            result = proxy_list(args)

            assert result.success is True
            mock_service.list_all_cards.assert_called_once()

            # Verify logging calls for card display
            mock_logger["info"].assert_called()

            # Check that table headers and totals were logged
            info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
            assert any("Card Name" in call for call in info_calls)
            assert any("TOTAL" in call for call in info_calls)

    def test_proxy_list_no_cards(self, mock_logger):
        """Test listing proxy cards when no cards exist."""
        args = argparse.Namespace()

        with patch(
            "netdecker.cli.commands.proxy.card_inventory_service"
        ) as mock_service:
            mock_service.list_all_cards.return_value = []

            result = proxy_list(args)

            assert result.success is True
            mock_logger["info"].assert_called_with("No proxy cards found.")

    def test_proxy_list_card_calculations(self, mock_logger):
        """Test that proxy list correctly calculates in-use cards."""
        from netdecker.models.card import Card

        # Mock cards with different availability
        mock_cards = [
            Card(
                name="Lightning Bolt", quantity_owned=4, quantity_available=2
            ),  # 2 in use
            Card(
                name="Counterspell", quantity_owned=3, quantity_available=3
            ),  # 0 in use
        ]

        args = argparse.Namespace()

        with patch(
            "netdecker.cli.commands.proxy.card_inventory_service"
        ) as mock_service:
            mock_service.list_all_cards.return_value = mock_cards

            result = proxy_list(args)

            assert result.success is True

            # Verify the total calculations in the logged output
            info_calls = [call[0][0] for call in mock_logger["info"].call_args_list]
            total_line = [call for call in info_calls if "TOTAL" in call][0]

            # Should show: Total owned=7, available=5, in_use=2
            assert "7" in total_line  # total owned
            assert "5" in total_line  # total available
            assert "2" in total_line  # total in use


class TestProxyRemove:
    """Test cases for proxy remove command."""

    def test_proxy_remove_success(self):
        """Test successful proxy card removal."""
        args = argparse.Namespace(card_entries=["2 Lightning Bolt"])

        # Mock parse_cardlist and card_inventory_service
        with (
            patch(
                "netdecker.cli.commands.proxy.parse_cardlist",
                return_value={"Lightning Bolt": 2},
            ),
            patch(
                "netdecker.cli.commands.proxy.card_inventory_service"
            ) as mock_service,
        ):
            result = proxy_remove(args)

            assert result.success is True
            assert "Removed 2 cards from inventory" in result.message
            mock_service.remove_cards.assert_called_once_with({"Lightning Bolt": 2})

    def test_proxy_remove_empty_cards(self):
        """Test proxy remove with empty card list."""
        args = argparse.Namespace(card_entries=[])

        with (
            patch("netdecker.cli.commands.proxy.parse_cardlist", return_value={}),
            patch(
                "netdecker.cli.commands.proxy.card_inventory_service"
            ) as _mock_service,
        ):
            result = proxy_remove(args)

            assert result.success is True
            assert "Removed 0 cards from inventory" in result.message
