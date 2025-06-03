"""Tests for NetDecker CLI argument parsing and routing."""

import argparse
from unittest.mock import patch

import pytest

from netdecker.cli.cli import parse_args, route_command, validate_args


class TestCLIParsing:
    """Test cases for CLI argument parsing."""

    @pytest.mark.parametrize(
        "args,expected",
        [
            (
                ["proxy", "add", "4 Lightning Bolt"],
                {
                    "command": "proxy",
                    "proxy_command": "add",
                    "card_entries": ["4 Lightning Bolt"],
                },
            ),
            (["proxy", "list"], {"command": "proxy", "proxy_command": "list"}),
            (
                ["proxy", "remove", "2 Counterspell"],
                {
                    "command": "proxy",
                    "proxy_command": "remove",
                    "card_entries": ["2 Counterspell"],
                },
            ),
            (["deck", "list"], {"command": "deck", "deck_command": "list"}),
            (
                ["deck", "show", "My Deck"],
                {"command": "deck", "deck_command": "show", "name": "My Deck"},
            ),
            (
                [
                    "deck",
                    "sync",
                    "Test Deck",
                    "https://example.com",
                    "--format",
                    "Modern",
                ],
                {
                    "command": "deck",
                    "deck_command": "sync",
                    "name": "Test Deck",
                    "url": "https://example.com",
                    "format": "Modern",
                },
            ),
        ],
    )
    def test_parse_args_valid(self, args, expected):
        """Test parsing of valid argument combinations."""
        with patch("sys.argv", ["netdecker"] + args):
            parsed = parse_args()

            for key, value in expected.items():
                assert getattr(parsed, key) == value

    def test_parse_args_no_command(self):
        """Test parsing with no command specified."""
        with patch("sys.argv", ["netdecker"]):
            parsed = parse_args()
            assert parsed.command is None

    def test_parse_args_help_handling(self):
        """Test that help arguments are handled gracefully."""
        with (
            patch("sys.argv", ["netdecker", "--help"]),
            patch("sys.exit") as mock_sys_exit,
        ):
            parse_args()
            mock_sys_exit.assert_called_once_with(0)


class TestCLIValidation:
    """Test cases for CLI argument validation."""

    @pytest.mark.parametrize(
        "args,expected_error",
        [
            (argparse.Namespace(command=None), "No command specified"),
            (
                argparse.Namespace(command="proxy", proxy_command=None),
                "No proxy subcommand specified",
            ),
            (
                argparse.Namespace(command="deck", deck_command=None),
                "No deck subcommand specified",
            ),
        ],
    )
    def test_validate_args_failures(self, args, expected_error):
        """Test validation failures for various argument combinations."""
        error = validate_args(args)

        assert error is not None
        assert expected_error in error

    @pytest.mark.parametrize(
        "command,subcommand",
        [
            ("proxy", "add"),
            ("proxy", "list"),
            ("proxy", "remove"),
            ("deck", "list"),
            ("deck", "show"),
            ("deck", "sync"),
            ("deck", "delete"),
            ("deck", "batch"),
        ],
    )
    def test_validate_args_valid_commands(self, command, subcommand):
        """Test validation passes for valid command combinations."""
        if command == "proxy":
            args = argparse.Namespace(command=command, proxy_command=subcommand)
        else:
            args = argparse.Namespace(command=command, deck_command=subcommand)

        error = validate_args(args)
        assert error is None


class TestCLIRouting:
    """Test cases for CLI command routing."""

    @pytest.mark.parametrize(
        "command,subcommand,handler_module",
        [
            ("proxy", "list", "netdecker.cli.commands.proxy"),
            ("deck", "list", "netdecker.cli.commands.deck"),
        ],
    )
    def test_route_command_valid(self, mock_db, command, subcommand, handler_module):
        """Test routing to valid command handlers."""
        if command == "proxy":
            args = argparse.Namespace(command=command, proxy_command=subcommand)
        else:
            args = argparse.Namespace(command=command, deck_command=subcommand)

        with patch(f"{handler_module}.handle_command") as mock_handle:
            route_command(args)
            mock_handle.assert_called_once_with(args)

    def test_route_command_unknown(self, mock_db, mock_logger):
        """Test routing with unknown command."""
        args = argparse.Namespace(command="unknown")

        route_command(args)

        mock_logger["error"].assert_called()
        error_calls = [call[0][0] for call in mock_logger["error"].call_args_list]
        assert any("Unknown command" in call for call in error_calls)

    def test_route_command_db_init_failure(self):
        """Test routing when database initialization fails."""
        args = argparse.Namespace(command="proxy", proxy_command="list")

        with (
            patch("netdecker.cli.cli.initialize_database", return_value=False),
            patch("netdecker.config.LOGGER.error") as mock_error,
        ):
            route_command(args)
            mock_error.assert_called_with("Failed to initialize database")
