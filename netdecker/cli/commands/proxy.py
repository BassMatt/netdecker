"""Proxy command handlers for NetDecker CLI."""

import argparse

from netdecker.cli.result import CommandResult, error, success
from netdecker.config import LOGGER
from netdecker.services import card_inventory_service
from netdecker.utils import parse_cardlist


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up the proxy command parser and its subcommands."""
    proxy_parser = subparsers.add_parser("proxy", help="Commands to manage proxy cards")
    proxy_subparsers = proxy_parser.add_subparsers(dest="proxy_command")

    # proxy add command
    proxy_add_parser = proxy_subparsers.add_parser(
        "add", help="Add proxy cards to the system"
    )
    proxy_add_parser.add_argument(
        "card_entries",
        nargs="+",
        help='Card entries in format "quantity cardname" (e.g., "4 Lightning Bolt")',
    )

    # proxy list command
    proxy_subparsers.add_parser("list", help="List all proxy cards")

    # proxy remove command
    proxy_remove_parser = proxy_subparsers.add_parser(
        "remove", help="Remove proxy cards from the system"
    )
    proxy_remove_parser.add_argument(
        "card_entries",
        nargs="+",
        help='Card entries in format "quantity cardname"',
    )

    # proxy clear command
    proxy_clear_parser = proxy_subparsers.add_parser(
        "clear", help="Remove ALL proxy cards from the system"
    )
    proxy_clear_parser.add_argument(
        "--confirm", action="store_true", help="Skip confirmation prompt"
    )


def handle_command(args: argparse.Namespace) -> None:
    """Route proxy subcommands to their appropriate handlers."""
    handlers = {
        "add": proxy_add,
        "list": proxy_list,
        "remove": proxy_remove,
        "clear": proxy_clear,
    }

    handler = handlers.get(args.proxy_command)
    if handler:
        result = handler(args)
        result.log()
        if result.exit_code != 0:
            exit(result.exit_code)
    else:
        result = error(f"Unknown proxy subcommand: {args.proxy_command}")
        result.log()
        exit(1)


def proxy_add(args: argparse.Namespace) -> CommandResult:
    """Add proxy cards to the system."""
    card_dict = parse_cardlist(args.card_entries)
    card_inventory_service.add_cards(card_dict)

    total_cards = sum(card_dict.values())
    return success(f"Added {total_cards} cards to inventory")


def proxy_list(args: argparse.Namespace) -> CommandResult:
    """List all proxy cards."""
    cards = card_inventory_service.list_all_cards()

    if not cards:
        LOGGER.info("No proxy cards found.")
        return success()

    LOGGER.info(f"{'Card Name':<40} | {'Owned':<6} | {'Available':<10} | {'In Use':<6}")
    LOGGER.info("-" * 70)

    total_owned = 0
    total_available = 0
    total_in_use = 0

    for card in sorted(cards, key=lambda c: c.name):
        in_use = card.quantity_owned - card.quantity_available
        total_owned += card.quantity_owned
        total_available += card.quantity_available
        total_in_use += in_use

        LOGGER.info(
            f"{card.name:<40} | {card.quantity_owned:<6} | "
            f"{card.quantity_available:<10} | {in_use:<6}"
        )

    LOGGER.info("-" * 70)
    LOGGER.info(
        f"{'TOTAL':<40} | {total_owned:<6} | {total_available:<10} | {total_in_use:<6}"
    )

    return success()


def proxy_remove(args: argparse.Namespace) -> CommandResult:
    """Remove proxy cards from the system."""
    card_dict = parse_cardlist(args.card_entries)
    card_inventory_service.remove_cards(card_dict)

    total_cards = sum(card_dict.values())
    return success(f"Removed {total_cards} cards from inventory")


def proxy_clear(args: argparse.Namespace) -> CommandResult:
    """Remove all proxy cards from the system."""
    # Get all cards first
    cards = card_inventory_service.list_all_cards()

    if not cards:
        return success("No proxy cards to remove")

    if not args.confirm:
        confirm = input(
            f"Are you sure you want to remove all {len(cards)} proxy cards? (y/n): "
        )
        if confirm.lower() != "y":
            return success("Operation cancelled")

    # Create a dictionary of all cards with their owned quantities
    all_cards = {card.name: card.quantity_owned for card in cards}

    try:
        card_inventory_service.remove_cards(all_cards)
        return success(f"Removed {len(cards)} proxy cards from inventory")
    except Exception as e:
        return error(f"Failed to remove cards: {e}")
