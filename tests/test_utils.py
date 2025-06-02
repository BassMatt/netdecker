"""Tests for NetDecker utility functions."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from netdecker.errors import (
    CardListInputError,
    DomainNotSupportedError,
    UnableToFetchDecklistError,
)
from netdecker.utils import (
    fetch_decklist,
    get_card_tokens,
    parse_cardlist,
    read_cardlist_from_file,
)


class TestReadCardlistFromFile:
    """Test cases for read_cardlist_from_file function."""

    def test_read_cardlist_from_file_success(self):
        """Test successfully reading a cardlist from a file."""
        cardlist_content = [
            "4 Lightning Bolt\n",
            "2 Counterspell\n",
            "1 Force of Will\n",
        ]

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.writelines(cardlist_content)
            temp_path = Path(f.name)

        try:
            result = read_cardlist_from_file(str(temp_path))
            assert result == cardlist_content
        finally:
            temp_path.unlink()

    def test_read_cardlist_from_file_empty(self):
        """Test reading an empty cardlist file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = read_cardlist_from_file(str(temp_path))
            assert result == []
        finally:
            temp_path.unlink()


class TestParseCardlist:
    """Test cases for parse_cardlist function."""

    @pytest.mark.parametrize(
        "card_lines,expected",
        [
            (["4 Lightning Bolt"], {"Lightning Bolt": 4}),
            (
                ["4 Lightning Bolt", "2 Counterspell"],
                {"Lightning Bolt": 4, "Counterspell": 2},
            ),
            (
                ["1 Force of Will", "3 Brainstorm"],
                {"Force of Will": 1, "Brainstorm": 3},
            ),
        ],
    )
    def test_parse_cardlist_valid(self, card_lines, expected):
        """Test parsing valid cardlists."""
        result = parse_cardlist(card_lines)
        assert result == expected

    def test_parse_cardlist_with_comments(self):
        """Test parsing cardlist with comments and empty lines."""
        card_lines = [
            "# This is a comment",
            "4 Lightning Bolt",
            "",
            "2 Counterspell",
            "# Another comment",
            "1 Force of Will",
        ]
        expected = {"Lightning Bolt": 4, "Counterspell": 2, "Force of Will": 1}

        result = parse_cardlist(card_lines)
        assert result == expected

    def test_parse_cardlist_duplicate_cards(self):
        """Test parsing cardlist with duplicate card entries."""
        card_lines = ["2 Lightning Bolt", "3 Lightning Bolt", "1 Counterspell"]
        expected = {"Lightning Bolt": 5, "Counterspell": 1}

        result = parse_cardlist(card_lines)
        assert result == expected

    @pytest.mark.parametrize(
        "invalid_lines",
        [
            ["4"],  # Missing card name
            [
                "4 Lightning Bolt",
                "4x Lightning Bolt",
            ],  # Non-numeric quantity that starts with digit
            ["4 Lightning Bolt", "4"],  # Mixed valid/invalid
        ],
    )
    def test_parse_cardlist_invalid_lines(self, invalid_lines):
        """Test parsing cardlist with invalid lines raises CardListInputError."""
        with pytest.raises(CardListInputError) as exc_info:
            parse_cardlist(invalid_lines)

        error = exc_info.value
        assert len(error.line_errors) > 0

    def test_parse_cardlist_empty_list(self):
        """Test parsing empty cardlist."""
        result = parse_cardlist([])
        assert result == {}

    def test_parse_cardlist_only_comments(self):
        """Test parsing cardlist with only comments and empty lines."""
        card_lines = ["# Comment 1", "", "# Comment 2", ""]
        result = parse_cardlist(card_lines)
        assert result == {}

    def test_parse_cardlist_skipped_lines(self):
        """Test that lines starting with non-digits are skipped."""
        card_lines = [
            "4 Lightning Bolt",
            "Lightning Bolt",  # No quantity - should be skipped
            "abc Invalid line",  # Non-digit start - should be skipped
            "2 Counterspell",
        ]
        expected = {"Lightning Bolt": 4, "Counterspell": 2}

        result = parse_cardlist(card_lines)
        assert result == expected


class TestFetchDecklist:
    """Test cases for fetch_decklist function."""

    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_cubecobra(self, mock_get):
        """Test fetching decklist from CubeCobra."""
        mock_response = Mock()
        mock_response.text = "4 Lightning Bolt\n2 Counterspell"
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        url = "https://www.cubecobra.com/cube/overview/MattHomeCube"

        with patch("netdecker.utils.parse_cardlist") as mock_parse:
            mock_parse.return_value = {"Lightning Bolt": 4, "Counterspell": 2}

            result = fetch_decklist(url)

            assert result == {"Lightning Bolt": 4, "Counterspell": 2}
            mock_get.assert_called_once_with(
                "https://www.cubecobra.com/cube/download/mtgo/MattHomeCube", timeout=30
            )

    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_mtggoldfish(self, mock_get):
        """Test fetching decklist from MTGGoldfish."""
        mock_response = Mock()
        mock_response.text = "3 Force of Will\n1 Black Lotus"
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        url = "https://www.mtggoldfish.com/deck/6732890#paper"

        with patch("netdecker.utils.parse_cardlist") as mock_parse:
            mock_parse.return_value = {"Force of Will": 3, "Black Lotus": 1}

            result = fetch_decklist(url)

            assert result == {"Force of Will": 3, "Black Lotus": 1}
            mock_get.assert_called_once_with(
                "https://www.mtggoldfish.com/deck/download/6732890", timeout=30
            )

    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_moxfield(self, mock_get):
        """Test fetching decklist from Moxfield."""
        # Mock the API response for getting export ID
        api_response = Mock()
        api_response.json.return_value = {"exportId": "test-export-id"}
        api_response.__bool__ = Mock(return_value=True)

        # Mock the actual decklist download
        deck_response = Mock()
        deck_response.text = "4 Lightning Bolt\n4 Counterspell"
        deck_response.apparent_encoding = "utf-8"

        mock_get.side_effect = [api_response, deck_response]

        url = "https://www.moxfield.com/decks/AahWutbE20GeNMt2ENLT7A"

        with patch("netdecker.utils.parse_cardlist") as mock_parse:
            mock_parse.return_value = {"Lightning Bolt": 4, "Counterspell": 4}

            result = fetch_decklist(url)

            assert result == {"Lightning Bolt": 4, "Counterspell": 4}
            assert mock_get.call_count == 2

    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_moxfield_no_export_id(self, mock_get):
        """Test Moxfield fetch when API response has no exportId."""
        api_response = Mock()
        api_response.json.return_value = {}  # No exportId
        api_response.__bool__ = Mock(return_value=True)

        mock_get.return_value = api_response

        url = "https://www.moxfield.com/decks/AahWutbE20GeNMt2ENLT7A"

        # Should still work, just without export ID in URL
        deck_response = Mock()
        deck_response.text = "4 Lightning Bolt"
        deck_response.apparent_encoding = "utf-8"

        mock_get.side_effect = [api_response, deck_response]

        with patch("netdecker.utils.parse_cardlist") as mock_parse:
            mock_parse.return_value = {"Lightning Bolt": 4}

            result = fetch_decklist(url)
            assert result == {"Lightning Bolt": 4}

    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_moxfield_api_failure(self, mock_get):
        """Test Moxfield fetch when API call fails."""
        api_response = Mock()
        api_response.__bool__ = Mock(return_value=False)  # API call failed
        mock_get.return_value = api_response

        url = "https://www.moxfield.com/decks/AahWutbE20GeNMt2ENLT7A"

        with pytest.raises(UnableToFetchDecklistError):
            fetch_decklist(url)

    def test_fetch_decklist_unsupported_domain(self):
        """Test fetching from unsupported domain raises DomainNotSupportedError."""
        url = "https://unsupported.com/deck/123"

        with pytest.raises(DomainNotSupportedError):
            fetch_decklist(url)

    @pytest.mark.parametrize(
        "domain,deck_id,expected_download_url",
        [
            (
                "www.cubecobra.com",
                "TestCube",
                "https://www.cubecobra.com/cube/download/mtgo/TestCube",
            ),
            (
                "www.mtggoldfish.com",
                "123456",
                "https://www.mtggoldfish.com/deck/download/123456",
            ),
        ],
    )
    @patch("netdecker.utils.requests.get")
    def test_fetch_decklist_url_construction(
        self, mock_get, domain, deck_id, expected_download_url
    ):
        """Test that download URLs are constructed correctly for different domains."""
        mock_response = Mock()
        mock_response.text = "4 Lightning Bolt"
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        url = f"https://{domain}/some/path/{deck_id}"

        with patch("netdecker.utils.parse_cardlist") as mock_parse:
            mock_parse.return_value = {"Lightning Bolt": 4}

            fetch_decklist(url)

            mock_get.assert_called_once_with(expected_download_url, timeout=30)


class TestGetCardTokens:
    """Test cases for get_card_tokens function."""

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_success(self, mock_get):
        """Test successfully getting tokens for cards."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "all_parts": [
                {"component": "token", "name": "Beast Token"},
                {"component": "card", "name": "Garruk Wildspeaker"},
                {"component": "token", "name": "Emblem Token"},
            ]
        }
        mock_get.return_value = mock_response

        result = get_card_tokens(["Garruk Wildspeaker"])

        expected = {"Beast Token": 1, "Emblem Token": 1}
        assert result == expected
        mock_get.assert_called_once()

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_no_tokens(self, mock_get):
        """Test getting tokens for card with no tokens."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No all_parts
        mock_get.return_value = mock_response

        result = get_card_tokens(["Lightning Bolt"])

        assert result == {}

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_api_failure(self, mock_get):
        """Test handling API failure gracefully."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_card_tokens(["Nonexistent Card"])

        assert result == {}

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_request_exception(self, mock_get):
        """Test handling request exceptions gracefully."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = get_card_tokens(["Lightning Bolt"])

        assert result == {}

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_multiple_cards(self, mock_get):
        """Test getting tokens for multiple cards."""

        def mock_get_side_effect(url, timeout):
            if "Garruk" in url:
                response = Mock()
                response.status_code = 200
                response.json.return_value = {
                    "all_parts": [{"component": "token", "name": "Beast Token"}]
                }
                return response
            elif "Lightning" in url:
                response = Mock()
                response.status_code = 200
                response.json.return_value = {}  # No tokens
                return response
            else:
                response = Mock()
                response.status_code = 404
                return response

        mock_get.side_effect = mock_get_side_effect

        result = get_card_tokens(["Garruk Wildspeaker", "Lightning Bolt"])

        assert result == {"Beast Token": 1}
        assert mock_get.call_count == 2

    @patch("netdecker.utils.requests.get")
    def test_get_card_tokens_duplicate_tokens(self, mock_get):
        """Test handling duplicate tokens from multiple cards."""

        def mock_get_side_effect(url, timeout):
            response = Mock()
            response.status_code = 200
            response.json.return_value = {
                "all_parts": [{"component": "token", "name": "Beast Token"}]
            }
            return response

        mock_get.side_effect = mock_get_side_effect

        result = get_card_tokens(["Card 1", "Card 2"])  # Both create Beast Token

        # Should keep the maximum count (1 in this case)
        assert result == {"Beast Token": 1}

    def test_get_card_tokens_empty_list(self):
        """Test getting tokens for empty card list."""
        result = get_card_tokens([])
        assert result == {}
