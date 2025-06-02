"""Tests for NetDecker error classes."""

import pytest

from netdecker.errors import (
    CardInsufficientQuantityError,
    CardListInputError,
    DomainNotSupportedError,
    Error,
    UnableToFetchDecklistError,
)


class TestBaseError:
    """Test cases for the base Error class."""

    def test_error_base_class(self):
        """Test that Error is a proper exception subclass."""
        error = Error("Test message")
        assert isinstance(error, Exception)
        assert str(error) == "Test message"


class TestCardListInputError:
    """Test cases for CardListInputError."""

    def test_cardlist_input_error_single_line(self):
        """Test CardListInputError with a single invalid line."""
        line_errors = ["4"]
        error = CardListInputError(line_errors)

        assert error.line_errors == line_errors
        error_str = str(error)
        assert "Error parsing provided card list" in error_str
        assert "<quantity> <cardname>" in error_str
        assert "4" in error_str
        assert "```" in error_str

    def test_cardlist_input_error_multiple_lines(self):
        """Test CardListInputError with multiple invalid lines."""
        line_errors = ["4", "Lightning", "invalid line"]
        error = CardListInputError(line_errors)

        assert error.line_errors == line_errors
        error_str = str(error)
        assert "Error parsing provided card list" in error_str
        for line in line_errors:
            assert line in error_str

    def test_cardlist_input_error_empty_lines(self):
        """Test CardListInputError with empty line errors."""
        line_errors = []
        error = CardListInputError(line_errors)

        assert error.line_errors == []
        error_str = str(error)
        assert "Error parsing provided card list" in error_str


class TestCardInsufficientQuantityError:
    """Test cases for CardInsufficientQuantityError."""

    def test_card_insufficient_quantity_error(self):
        """Test CardInsufficientQuantityError string representation."""
        error = CardInsufficientQuantityError("Lightning Bolt", 4, 2)

        assert error.name == "Lightning Bolt"
        assert error.requested == 4
        assert error.quantity == 2

        error_str = str(error)
        assert (
            "Insufficient quantity to perform action on 'Lightning Bolt'" in error_str
        )
        assert "requested 4 but only 2 available" in error_str

    @pytest.mark.parametrize(
        "name,requested,quantity",
        [
            ("Counterspell", 5, 3),
            ("Force of Will", 1, 0),
            ("Black Lotus", 10, 7),
        ],
    )
    def test_card_insufficient_quantity_error_parametrized(
        self, name, requested, quantity
    ):
        """Test CardInsufficientQuantityError with various inputs."""
        error = CardInsufficientQuantityError(name, requested, quantity)

        assert error.name == name
        assert error.requested == requested
        assert error.quantity == quantity

        error_str = str(error)
        assert f"Insufficient quantity to perform action on '{name}'" in error_str
        assert f"requested {requested} but only {quantity} available" in error_str


class TestDomainNotSupportedError:
    """Test cases for DomainNotSupportedError."""

    def test_domain_not_supported_error(self):
        """Test DomainNotSupportedError string representation."""
        error = DomainNotSupportedError()

        error_str = str(error)
        assert "Domain not supported" in error_str
        assert "cubecobra.com" in error_str
        assert "mtggoldfish.com" in error_str
        assert "moxfield.com" in error_str


class TestUnableToFetchDecklistError:
    """Test cases for UnableToFetchDecklistError."""

    def test_unable_to_fetch_decklist_error(self):
        """Test UnableToFetchDecklistError string representation."""
        error = UnableToFetchDecklistError()

        error_str = str(error)
        assert "Unable to fetch decklist from the provided URL" in error_str
