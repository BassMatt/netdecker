"""Deck management commands for NetDecker CLI."""

import argparse
import sys

from netdecker.cli.helpers import extract_deck_configs, find_deck, load_yaml_config
from netdecker.cli.result import CommandResult, error, info, success, warning
from netdecker.config import LOGGER
from netdecker.services import (
    card_allocation_service,
    card_inventory_service,
    decklist_service,
)
from netdecker.workflows.deck_management import (
    BatchUpdatePreview,
    DeckManagementWorkflow,
    DeckUpdatePreview,
)


def setup_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up the deck command parser and its subcommands."""
    deck_parser = subparsers.add_parser("deck", help="Deck management commands")
    deck_subparsers = deck_parser.add_subparsers(dest="deck_command")

    # deck list command - list all tracked decks
    deck_subparsers.add_parser("list", help="List all tracked decks")

    # deck show command - show cards in a specific deck
    show_parser = deck_subparsers.add_parser(
        "show", help="Show cards in a specific deck"
    )
    show_parser.add_argument("name", help="Name of the deck to show")
    show_parser.add_argument(
        "--format", help="Format of the deck (optional, for disambiguation)"
    )

    # deck add command - add a new deck (simplified from update)
    add_parser = deck_subparsers.add_parser("add", help="Add a new deck")
    add_parser.add_argument("name", help="Name for the deck")
    add_parser.add_argument("url", help="URL of the decklist")
    add_parser.add_argument(
        "--format",
        required=True,
        help="Format of the deck (e.g., Modern, Vintage, Cube)",
    )

    # deck update command - update an existing deck
    update_parser = deck_subparsers.add_parser("update", help="Update an existing deck")
    update_parser.add_argument("name", help="Name of the deck to update")
    update_parser.add_argument(
        "url", nargs="?", help="New URL (uses stored URL if omitted)"
    )
    update_parser.add_argument(
        "--format", help="Format of the deck (for disambiguation if needed)"
    )
    update_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview changes without applying them",
    )

    # deck delete command - delete a deck
    delete_parser = deck_subparsers.add_parser(
        "delete", help="Delete a deck and free its cards"
    )
    delete_parser.add_argument("name", help="Name of the deck to delete")
    delete_parser.add_argument(
        "--format", help="Format of the deck (for disambiguation if needed)"
    )
    delete_parser.add_argument(
        "--confirm", action="store_true", help="Skip confirmation prompt"
    )

    # deck batch command - process multiple decks from YAML
    batch_parser = deck_subparsers.add_parser(
        "batch", help="Process multiple decks from YAML file"
    )
    batch_parser.add_argument("yaml_file", help="YAML file with deck configurations")
    batch_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview changes without applying them",
    )
    batch_parser.add_argument(
        "--order-file",
        help="Write order to file (works with both preview and apply)",
    )
    batch_parser.add_argument(
        "--no-tokens",
        action="store_true",
        help="Don't include tokens in order",
    )

    # deck order command - generate order for missing cards
    order_parser = deck_subparsers.add_parser(
        "order", help="Generate order for missing cards"
    )
    order_source = order_parser.add_mutually_exclusive_group(required=True)
    order_source.add_argument("--deck", help="Generate order for a specific deck")
    order_source.add_argument("--url", help="Generate order for a decklist URL")
    order_source.add_argument("--yaml", help="Generate order for decks in YAML file")
    order_parser.add_argument("--format", help="Format for URL-based orders")
    order_parser.add_argument("--output", "-o", help="Output file (defaults to stdout)")
    order_parser.add_argument(
        "--no-tokens",
        action="store_true",
        help="Don't include tokens in order",
    )


def handle_command(args: argparse.Namespace) -> None:
    """Route deck subcommands to their appropriate handlers."""
    workflow = DeckManagementWorkflow(
        card_inventory_service, card_allocation_service, decklist_service
    )

    handlers = {
        "list": deck_list,
        "show": deck_show,
        "add": deck_add,
        "update": deck_update,
        "delete": deck_delete,
        "batch": deck_batch,
        "order": deck_order,
    }

    handler = handlers.get(args.deck_command)
    if handler:
        result = handler(args, workflow)
        result.log()
        if result.exit_code != 0:
            exit(result.exit_code)
    else:
        result = error(f"Unknown deck subcommand: {args.deck_command}")
        result.log()
        exit(1)


def deck_list(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """List all tracked decks."""
    decklists = workflow.decklists.list_decklists()

    if not decklists:
        return info("No tracked decks found.")

    LOGGER.info(f"{'Format':<12} | {'Name':<25} | {'Last Updated':<20} | {'URL':<50}")
    LOGGER.info("-" * 110)

    for deck in sorted(decklists, key=lambda d: (d.format, d.name)):
        updated_str = deck.updated_at.strftime("%Y-%m-%d %H:%M")
        url_display = deck.url[:47] + "..." if len(deck.url) > 50 else deck.url
        LOGGER.info(
            f"{deck.format:<12} | {deck.name:<25} | "
            f"{updated_str:<20} | {url_display:<50}"
        )

    return success()


def deck_show(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Show cards in a specific deck."""
    deck = find_deck(args.name, args.format, workflow, log_error=False)
    if not deck:
        return error(f"Deck '{args.name}' not found")

    cards = workflow.decklists.get_decklist_cards(deck.id)

    LOGGER.info(f"Deck: {deck.name} ({deck.format})")
    LOGGER.info(f"URL: {deck.url}")
    LOGGER.info(f"Total Cards: {sum(cards.values())}")
    LOGGER.info("")
    LOGGER.info(f"{'Quantity':<8} | {'Card Name':<40}")
    LOGGER.info("-" * 50)

    for card_name in sorted(cards.keys()):
        LOGGER.info(f"{cards[card_name]:<8} | {card_name:<40}")

    return success()


def deck_add(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Add a new deck."""
    # Check if deck already exists (suppress find_deck error for custom message)
    existing = find_deck(args.name, args.format, workflow, log_error=False)
    if existing:
        return error(f"Deck '{args.name}' already exists for format '{args.format}'")

    # Apply the deck (no preview for add)
    result = workflow.apply_deck_update(args.url, args.format, args.name)

    if result.errors:
        return error(result.errors[0])

    if result.cards_to_order:
        return warning(
            f"Added deck '{args.name}' ({args.format}) - "
            f"need to order {result.total_cards_to_order} cards"
        )
    else:
        return success(f"Added deck '{args.name}' ({args.format})")


def deck_update(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Update an existing deck."""
    deck = find_deck(args.name, args.format, workflow, log_error=False)
    if not deck:
        return error(f"Deck '{args.name}' not found")

    # Use provided URL or stored URL
    url = args.url if args.url else deck.url

    # Preview or apply
    if args.preview:
        LOGGER.info(f"Previewing update for '{deck.name}'...")
        result = workflow.preview_deck_update(url, deck.format, deck.name)
    else:
        LOGGER.info(f"Updating '{deck.name}'...")
        result = workflow.apply_deck_update(url, deck.format, deck.name)

    # Display results
    workflow.write_preview_to_file(result, sys.stdout)

    if result.errors:
        return error(result.errors[0])

    if args.preview:
        LOGGER.info("\nThis was a preview. Remove --preview to apply changes.")
        return success()

    return success(f"Updated deck '{deck.name}'")


def deck_delete(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Delete a deck and free its cards."""
    deck = find_deck(args.name, args.format, workflow, log_error=False)
    if not deck:
        return error(f"Deck '{args.name}' not found")

    if not args.confirm:
        response = input(
            f"Delete deck '{deck.name}' ({deck.format}) and free its cards? (y/N): "
        )
        if response.lower() != "y":
            return info("Cancelled")

    # Release allocations first
    workflow.allocation.release_decklist_allocation(deck.id)

    # Delete the deck
    success_flag = workflow.decklists.delete_decklist(deck.id)

    if success_flag:
        return success(f"Deleted deck '{deck.name}' and freed its cards")
    else:
        return error(f"Failed to delete deck '{deck.name}'")


def deck_batch(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Process multiple decks from YAML file."""
    config = load_yaml_config(args.yaml_file)
    if not config:
        return error(f"Failed to load YAML file: {args.yaml_file}")

    deck_configs = extract_deck_configs(config)
    if not deck_configs:
        return error("No decks found in YAML file")

    # Process batch
    if args.preview:
        LOGGER.info(f"Previewing updates for {len(deck_configs)} decks...")
        result = workflow.preview_batch_update(deck_configs)
    else:
        LOGGER.info(f"Updating {len(deck_configs)} decks...")
        result = workflow.apply_batch_update(deck_configs)

    # Display results
    workflow.write_preview_to_file(result, sys.stdout)

    # Write order file if requested
    if args.order_file and result.total_order:
        with open(args.order_file, "w") as f:
            workflow.write_order_to_mpcfill(
                result,
                f,
                include_tokens=not args.no_tokens,
                fetch_tokens=not args.no_tokens,
            )
        LOGGER.info(f"✓ Order written to {args.order_file}")

    # Check for errors
    error_count = sum(1 for update in result.deck_updates if update.errors)
    if error_count > 0:
        return warning(f"{error_count} decks had errors")

    if args.preview:
        LOGGER.info("\nThis was a preview. Remove --preview to apply changes.")
        return success()

    return success(f"Updated {len(deck_configs)} decks")


def deck_order(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Generate order for missing cards."""
    preview: DeckUpdatePreview | BatchUpdatePreview

    if args.deck:
        # Order for existing deck
        deck = find_deck(args.deck, None, workflow, log_error=False)
        if not deck:
            return error(f"Deck '{args.deck}' not found")

        preview = workflow.preview_deck_update(deck.url, deck.format, deck.name)

    elif args.url:
        # Order for URL
        if not args.format:
            return error("--format is required when using --url")

        preview = workflow.preview_deck_update(args.url, args.format, "temp-order")

    elif args.yaml:
        # Order for YAML file
        config = load_yaml_config(args.yaml)
        if not config:
            return error(f"Failed to load YAML file: {args.yaml}")

        deck_configs = extract_deck_configs(config)
        preview = workflow.preview_batch_update(deck_configs)

    # Generate order output
    if args.output:
        with open(args.output, "w") as f:
            workflow.write_order_to_mpcfill(
                preview,
                f,
                include_tokens=not args.no_tokens,
                fetch_tokens=not args.no_tokens,
            )
        return success(f"Order written to {args.output}")
    else:
        # Write to stdout
        workflow.write_order_to_mpcfill(
            preview,
            sys.stdout,
            include_tokens=not args.no_tokens,
            fetch_tokens=not args.no_tokens,
        )

    return success()
