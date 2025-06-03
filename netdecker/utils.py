"""Utility functions for NetDecker."""

from collections import Counter
from urllib.parse import quote, urlparse

import requests

from .config import LOGGER
from .errors import (
    CardListInputError,
    DomainNotSupportedError,
    UnableToFetchDecklistError,
)


def read_cardlist_from_file(path: str) -> list[str]:
    """Read a cardlist from a file."""
    with open(path) as f:
        return f.readlines()


def fetch_decklist(decklist_url: str) -> dict[str, int]:
    """
    Example URLs:

    CubeCobra: https://www.cubecobra.com/cube/overview/MattHomeCube
    MTGGoldfish: https://www.mtggoldfish.com/deck/6732890#paper
    Moxfield: https://www.moxfield.com/decks/AahWutbE20GeNMt2ENLT7A
    """
    parsed_url = urlparse(decklist_url)

    domain = parsed_url.netloc
    deck_id = parsed_url.path.split("/")[-1]
    LOGGER.info(f"Parsed URL: {decklist_url}, Deck ID: {deck_id}, Domain: {domain}")

    # Normalize domain by removing www. prefix if present
    normalized_domain = (
        domain.replace("www.", "") if domain.startswith("www.") else domain
    )

    download_url = ""
    if normalized_domain == "cubecobra.com":
        download_url = f"https://www.cubecobra.com/cube/download/mtgo/{deck_id}"
    elif normalized_domain == "mtggoldfish.com":
        download_url = f"https://www.mtggoldfish.com/deck/download/{deck_id}"
    elif normalized_domain == "moxfield.com":
        resp = requests.get(
            f"https://api2.moxfield.com/v2/decks/all/{deck_id}", timeout=30
        )
        if not resp:
            raise UnableToFetchDecklistError()
        resp_json = resp.json()
        if "exportId" in resp_json:
            download_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}/export?format=mtgo&exportId={resp_json['exportId']}"
    else:
        raise DomainNotSupportedError()

    # A GET request to the API
    response = requests.get(download_url, timeout=30)
    response.encoding = response.apparent_encoding

    # Parse the decklist
    decklist = parse_cardlist(response.text.splitlines())

    LOGGER.info(f"Decklist retrieved: {sum(decklist.values())} cards found")

    return decklist


def parse_cardlist(card_list: list[str]) -> dict[str, int]:
    """
    Parses and validates provided cardlist is in MTGO format and contains
    valid cardnames.

    Returns: Dictionary that maps CardName -> Count
    """
    line_errors: list[str] = []
    cards: Counter[str] = Counter()
    for line in card_list:
        if line.startswith("#") or line == "" or not line[0].isdigit():
            # skip non-cardlines
            continue

        split = line.strip().split(" ", 1)

        if len(split) != 2:
            line_errors.append(line)
            continue

        if not split[0].isdigit():
            line_errors.append(line)
            continue

        quantity, card_name = int(split[0]), split[1]

        cards[card_name] += quantity

    if len(line_errors) > 0:
        raise CardListInputError(line_errors)
    else:
        return dict(cards)


def get_card_tokens(card_names: list[str]) -> dict[str, int]:
    """
    Query Scryfall API to find tokens associated with cards in the list.
    Returns a dictionary of token names to suggested quantities.
    """
    tokens: dict[str, int] = {}

    for card_name in card_names:
        try:
            url = f"https://api.scryfall.com/cards/named?exact={quote(card_name)}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                continue

            data = response.json()
            if "all_parts" in data:
                for part in data["all_parts"]:
                    if part["component"] == "token":
                        token_name = str(part["name"])
                        # Suggest 1 token per card that creates it
                        # (user can adjust if needed)
                        tokens[token_name] = max(tokens.get(token_name, 0), 1)
        except Exception as e:
            LOGGER.warning(f"Failed to fetch token info for {card_name}: {e}")
            continue

    return tokens
