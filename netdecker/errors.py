"""Exception classes for NetDecker."""


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class CardListInputError(Error):
    """
    Exception raised for errors in parsing card lists.
    Used when parsing MTGO format card lists.
    """

    def __init__(self, line_errors: list[str]) -> None:
        self.line_errors = line_errors

    def __str__(self) -> str:
        message = (
            "Error parsing provided card list.\n\n"
            "Please ensure all lines follow the format: <quantity> <cardname>\n\n"
            "The following lines raised errors:\n```\n"
        )
        message += "\n".join(self.line_errors)
        message += "\n```"
        return message


class CardInsufficientQuantityError(Error):
    """
    Exception raised when trying to remove more cards than available.
    Used by service layer for data integrity.
    """

    def __init__(self, name: str, requested: int, quantity: int) -> None:
        self.name = name
        self.requested = requested
        self.quantity = quantity

    def __str__(self) -> str:
        return (
            f"Insufficient quantity to perform action on '{self.name}': "
            f"requested {self.requested} but only {self.quantity} available"
        )


class DomainNotSupportedError(Error):
    """Exception raised when a decklist URL domain is not supported."""

    def __str__(self) -> str:
        return (
            "Domain not supported. "
            "Supported domains: cubecobra.com, mtggoldfish.com, moxfield.com"
        )


class UnableToFetchDecklistError(Error):
    """Exception raised when unable to fetch a decklist from a URL."""

    def __str__(self) -> str:
        return "Unable to fetch decklist from the provided URL"
