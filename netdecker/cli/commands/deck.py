"""Deck management commands for NetDecker CLI."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from netdecker.cli.helpers import extract_deck_configs, find_deck, load_yaml_config
from netdecker.cli.result import CommandResult, error, info, success, warning
from netdecker.config import LOGGER
from netdecker.services import (
    card_allocation_service,
    card_inventory_service,
    decklist_service,
)
from netdecker.workflows.deck_management import (
    DeckManagementWorkflow,
    DeckUpdatePreview,
)


def _create_deck_output_dir(
    base_output_dir: Path, deck_format: str, deck_name: str
) -> Path:
    """Create a dated output directory for a specific deck."""
    # Sanitize deck name for filesystem
    safe_deck_name = deck_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{deck_format.lower()}-{safe_deck_name}-{timestamp}"

    deck_output_dir = base_output_dir / dir_name
    deck_output_dir.mkdir(parents=True, exist_ok=True)

    return deck_output_dir


def _create_batch_output_dir(base_output_dir: Path) -> Path:
    """Create a dated output directory for batch operations."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"batch-{timestamp}"

    batch_output_dir = base_output_dir / dir_name
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    return batch_output_dir


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

    # deck sync command - unified add/update command
    sync_parser = deck_subparsers.add_parser(
        "sync", help="Sync a deck (adds if new, updates if exists)"
    )
    sync_parser.add_argument("name", help="Name of the deck")
    sync_parser.add_argument("url", help="URL of the decklist")
    sync_parser.add_argument(
        "--format",
        help="Format of the deck (required for new decks, optional for existing)",
    )
    sync_parser.add_argument(
        "--save",
        action="store_true",
        help="Save changes to database and generate all output files (defaults to preview mode)",
    )
    sync_parser.add_argument(
        "--output",
        "-o",
        help="Output directory for generated files (required with --save)",
    )
    sync_parser.add_argument(
        "--no-tokens",
        action="store_true",
        help="Don't include tokens in order files",
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
        "--save",
        action="store_true",
        help="Save changes to database and generate all output files (defaults to preview mode)",
    )
    batch_parser.add_argument(
        "--output",
        "-o",
        help="Output directory for generated files (required with --save)",
    )
    batch_parser.add_argument(
        "--no-tokens",
        action="store_true",
        help="Don't include tokens in order files",
    )


def _validate_output_args(args: argparse.Namespace) -> str | None:
    """Validate output-related arguments. Returns error message if invalid."""
    # Sync and batch commands only use --save (default to preview mode)
    if args.deck_command in ["sync", "batch"]:
        save = getattr(args, "save", False)

        # If save mode, require output directory
        if save and not getattr(args, "output", None):
            return "--output directory is required when using --save"

    # Validate output directory exists if provided
    output = getattr(args, "output", None)
    if output:
        output_path = Path(output)
        if not output_path.exists():
            return f"Output directory '{output}' does not exist"
        if not output_path.is_dir():
            return f"Output path '{output}' is not a directory"

    return None


def handle_command(args: argparse.Namespace) -> None:
    """Route deck subcommands to their appropriate handlers."""
    # Validate output arguments first
    validation_error = _validate_output_args(args)
    if validation_error:
        result = error(validation_error)
        result.log()
        exit(1)

    workflow = DeckManagementWorkflow(
        card_inventory_service, card_allocation_service, decklist_service
    )

    handlers = {
        "list": deck_list,
        "show": deck_show,
        "sync": deck_sync,
        "delete": deck_delete,
        "batch": deck_batch,
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


def _generate_swap_file(
    deck_name: str, preview: "DeckUpdatePreview", deck_output_dir: Path
) -> None:
    """Generate a swap file with cards to add and remove."""
    swap_filename = "swaps.txt"
    swap_path = deck_output_dir / swap_filename

    try:
        with open(swap_path, "w") as f:
            f.write(f"=== Deck Swaps for {deck_name} ===\n\n")

            if preview.swaps.cards_to_remove:
                f.write("Cards to Remove:\n")
                for card in sorted(preview.swaps.cards_to_remove.keys()):
                    qty = preview.swaps.cards_to_remove[card]
                    f.write(f"-{qty} {card}\n")
                f.write("\n")

            if preview.swaps.cards_to_add:
                # Separate cards to add into available vs need to order
                cards_need_order = set(preview.cards_to_order.keys())
                cards_available = {}
                cards_to_order = {}

                for card, qty in preview.swaps.cards_to_add.items():
                    if card in cards_need_order:
                        # This card needs to be ordered
                        order_qty = preview.cards_to_order[card]
                        if qty > order_qty:
                            # Some available, some need ordering
                            cards_available[card] = qty - order_qty
                            cards_to_order[card] = order_qty
                        else:
                            # All need ordering
                            cards_to_order[card] = qty
                    else:
                        # All cards are available
                        cards_available[card] = qty

                if cards_available:
                    f.write("Cards to Add (Already Available):\n")
                    for card in sorted(cards_available.keys()):
                        qty = cards_available[card]
                        f.write(f"+{qty} {card}\n")
                    f.write("\n")

                if cards_to_order:
                    f.write("Cards to Add (Ordered):\n")
                    for card in sorted(cards_to_order.keys()):
                        qty = cards_to_order[card]
                        f.write(f"+{qty} {card}\n")
                    f.write("\n")

            if not preview.swaps.has_changes:
                f.write("No changes needed.\n")

        LOGGER.info(f"✓ Swap file written to {swap_path}")
    except Exception as e:
        LOGGER.error(f"Failed to write swap file: {e}")


def deck_sync(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Sync a deck (adds if new, updates if exists)."""
    deck = find_deck(args.name, args.format, workflow, log_error=False)
    is_new_deck = deck is None

    if deck:
        # Update existing deck
        LOGGER.info(f"Updating existing deck '{deck.name}'...")
        deck_format = deck.format
        deck_name = deck.name
    else:
        # Add new deck - format is required for new decks
        if not args.format:
            return error("--format is required when adding a new deck")
        LOGGER.info(f"Adding new deck '{args.name}'...")
        deck_format = args.format
        deck_name = args.name

    if args.save:
        # Save mode - apply changes and generate files
        result = workflow.apply_deck_update(args.url, deck_format, deck_name)

        # Display condensed results for save mode
        workflow.write_preview_to_file(result, sys.stdout, save_mode=True)

        # Only exit early if there are actual errors (not just info messages)
        actual_errors = [
            error for error in result.errors if not error.startswith("Info:")
        ]
        if actual_errors:
            return error(actual_errors[0])

        # Generate output files if save mode and output directory specified
        if args.output:
            base_output_dir = Path(args.output)
            deck_output_dir = _create_deck_output_dir(
                base_output_dir, deck_format, deck_name
            )

            # Generate swap file
            _generate_swap_file(deck_name, result, deck_output_dir)

            # Generate order file
            if result.cards_to_order:
                order_filename = "order.txt"
                order_path = deck_output_dir / order_filename
                try:
                    with open(order_path, "w") as f:
                        workflow.write_order_to_mpcfill(
                            result,
                            f,
                            include_tokens=not args.no_tokens,
                            fetch_tokens=not args.no_tokens,
                        )
                    LOGGER.info(f"✓ Order written to {order_path}")
                except Exception as e:
                    LOGGER.error(f"Failed to write order file: {e}")

            # Generate cube CSV for Cube format decks
            if deck_format.lower() == "cube":
                # For new decks, we need to find the deck again to get its ID
                if is_new_deck:
                    deck = find_deck(deck_name, deck_format, workflow, log_error=False)

                if deck:
                    cube_path = deck_output_dir / "cube.csv"
                    try:
                        with open(cube_path, "w") as f:
                            workflow.write_cube_csv(deck.id, f)
                        LOGGER.info(f"✓ Cube CSV written to {cube_path}")
                    except Exception as e:
                        LOGGER.error(f"Failed to write cube CSV: {e}")

        if result.cards_to_order:
            action = "Added" if is_new_deck else "Updated"
            return warning(
                f"{action} deck '{deck_name}' ({deck_format}) - "
                f"need to order {result.total_cards_to_order} cards"
            )
        else:
            action = "Added" if is_new_deck else "Updated"
            return success(f"{action} deck '{deck_name}' ({deck_format})")
    else:
        # Preview mode (default) - don't save to database
        if deck:
            result = workflow.preview_deck_update(args.url, deck.format, deck.name)
        else:
            if not args.format:
                return error("--format is required when adding a new deck")
            result = workflow.preview_deck_update(args.url, args.format, args.name)

        # Display results
        workflow.write_preview_to_file(result, sys.stdout)

        LOGGER.info(
            "\nThis was a preview. Use --save to apply changes and generate files."
        )
        return success()


def deck_delete(
    args: argparse.Namespace, workflow: DeckManagementWorkflow
) -> CommandResult:
    """Delete a deck and free its cards."""
    deck = find_deck(args.name, args.format, workflow, log_error=False)
    if not deck:
        return error(f"Deck '{args.name}' not found")

    # Get cards that would be released
    deck_cards = workflow.decklists.get_decklist_cards(deck.id)

    if not args.confirm:
        response = input(
            f"Delete deck '{deck.name}' ({deck.format}) and free its cards? (y/N): "
        )
        if response.lower() != "y":
            return info("Cancelled")

        # Ask if user wants to also remove proxy cards
        if deck_cards:
            remove_proxies = input(
                f"Also remove {len(deck_cards)} proxy cards from inventory? This will permanently delete them. (y/N): "
            )
            remove_proxy_cards = remove_proxies.lower() == "y"
        else:
            remove_proxy_cards = False
    else:
        remove_proxy_cards = False

    # Release allocations first
    workflow.allocation.release_decklist_allocation(deck.id)

    # Remove proxy cards if requested
    if remove_proxy_cards:
        cards_to_remove = {}
        for card_name in deck_cards.keys():
            # Get the card to find its owned quantity
            card = workflow.inventory.get_card(card_name)
            if card:
                cards_to_remove[card_name] = card.quantity_owned

        if cards_to_remove:
            try:
                workflow.inventory.remove_cards(cards_to_remove)
                removed_count = len(cards_to_remove)
                LOGGER.info(f"Removed {removed_count} proxy cards from inventory")
            except Exception as e:
                LOGGER.warning(f"Failed to remove some proxy cards: {e}")
                removed_count = 0
        else:
            removed_count = 0

    # Delete the deck
    success_flag = workflow.decklists.delete_decklist(deck.id)

    if success_flag:
        message = f"Deleted deck '{deck.name}' and freed its cards"
        if remove_proxy_cards:
            message += f" (also removed {removed_count} proxy cards)"
        return success(message)
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

    if args.save:
        # Save mode - apply changes and generate files
        LOGGER.info(f"Updating {len(deck_configs)} decks...")
        result = workflow.apply_batch_update(deck_configs)

        # Display condensed results for save mode
        workflow.write_preview_to_file(result, sys.stdout, save_mode=True)

        # Generate output files if save mode and output directory specified
        if args.output:
            base_output_dir = Path(args.output)
            batch_output_dir = _create_batch_output_dir(base_output_dir)

            # Generate swap files for each deck in individual subdirectories
            for deck_update in result.deck_updates:
                deck_subdir = (
                    batch_output_dir
                    / f"{deck_update.deck_format.lower()}-{deck_update.deck_name.replace(' ', '_')}"
                )
                deck_subdir.mkdir(parents=True, exist_ok=True)
                _generate_swap_file(deck_update.deck_name, deck_update, deck_subdir)

            # Generate batch order file
            if result.total_order:
                order_filename = "batch_order.txt"
                order_path = batch_output_dir / order_filename
                try:
                    with open(order_path, "w") as f:
                        workflow.write_order_to_mpcfill(
                            result,
                            f,
                            include_tokens=not args.no_tokens,
                            fetch_tokens=not args.no_tokens,
                        )
                    LOGGER.info(f"✓ Order written to {order_path}")
                except Exception as e:
                    LOGGER.error(f"Failed to write order file: {e}")

            # Generate cube CSV for any cube format decks
            cube_decks = [
                config for config in deck_configs if config["format"].lower() == "cube"
            ]
            if cube_decks:
                cube_path = batch_output_dir / "cubes.csv"
                try:
                    # For batch operations, we'll combine all cube decks into one CSV
                    # by writing the first cube deck found
                    for deck_config in cube_decks:
                        deck = find_deck(
                            deck_config["name"],
                            deck_config["format"],
                            workflow,
                            log_error=False,
                        )
                        if deck:
                            with open(cube_path, "w") as f:
                                workflow.write_cube_csv(deck.id, f)
                            LOGGER.info(f"✓ Cube CSV written to {cube_path}")
                            break  # Only write the first cube deck
                except Exception as e:
                    LOGGER.error(f"Failed to write cube CSV: {e}")

        # Check for errors
        error_count = sum(1 for update in result.deck_updates if update.errors)
        if error_count > 0:
            return warning(f"{error_count} decks had errors")

        return success(f"Updated {len(deck_configs)} decks")
    else:
        # Preview mode (default) - don't save to database
        LOGGER.info(f"Previewing updates for {len(deck_configs)} decks...")
        result = workflow.preview_batch_update(deck_configs)

        # Display results
        workflow.write_preview_to_file(result, sys.stdout)

        LOGGER.info(
            "\nThis was a preview. Use --save to apply changes and generate files."
        )
        return success()
