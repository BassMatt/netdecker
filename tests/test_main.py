"""Tests for NetDecker main entry point."""

from unittest.mock import Mock, patch

import pytest

from netdecker.main import cli_main, main


class TestMain:
    """Test cases for main entry point functions."""

    def test_main_success(self, mock_db):
        """Test successful command execution."""
        with (
            patch("netdecker.main.parse_args") as mock_parse,
            patch("netdecker.main.validate_args") as mock_validate,
            patch("netdecker.main.route_command") as mock_route,
        ):
            mock_parse.return_value = Mock()
            mock_validate.return_value = None  # No validation errors
            mock_route.return_value = None

            result = main()

            assert result == 0
            mock_parse.assert_called_once()
            mock_validate.assert_called_once()
            mock_route.assert_called_once()

    def test_main_validation_error(self, mock_db):
        """Test main with validation error."""
        with (
            patch("netdecker.main.parse_args") as mock_parse,
            patch("netdecker.main.validate_args") as mock_validate,
            patch("netdecker.main.route_command") as mock_route,
        ):
            mock_parse.return_value = Mock()
            mock_validate.return_value = "Invalid arguments"

            result = main()

            assert result == 1
            mock_parse.assert_called_once()
            mock_validate.assert_called_once()
            mock_route.assert_not_called()

    @pytest.mark.parametrize(
        "exception,exit_code,expected_result",
        [
            (SystemExit(2), 2, 2),
            (SystemExit(None), None, 1),
            (Exception("Test error"), None, 1),
        ],
    )
    def test_main_exceptions(self, mock_db, exception, exit_code, expected_result):
        """Test main with various exception types."""
        with (
            patch("netdecker.main.parse_args") as mock_parse,
            patch("netdecker.main.validate_args") as mock_validate,
            patch("netdecker.main.route_command") as mock_route,
        ):
            mock_parse.return_value = Mock()
            mock_validate.return_value = None
            mock_route.side_effect = exception

            result = main()

            assert result == expected_result

    def test_cli_main(self):
        """Test CLI main entry point."""
        with (
            patch("netdecker.main.main", return_value=0) as mock_main,
            patch("sys.exit") as mock_sys_exit,
        ):
            cli_main()

            mock_main.assert_called_once()
            mock_sys_exit.assert_called_once_with(0)
