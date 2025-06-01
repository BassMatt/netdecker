"""Command modules for NetDecker CLI."""

from .commands import deck, proxy

# Registry of all command modules
COMMAND_MODULES = [
    proxy,  # Card inventory management
    deck,  # Deck management (add, update, delete, list, show, order, batch)
]


def setup_all_parsers(subparsers):
    """Set up all command parsers by calling each module's setup_parser function."""
    for module in COMMAND_MODULES:
        module.setup_parser(subparsers)
