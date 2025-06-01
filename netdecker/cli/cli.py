import argparse

from netdecker.cli import setup_all_parsers
from netdecker.cli.commands import deck, proxy
from netdecker.config import LOGGER
from netdecker.db import initialize_database


def parse_args() -> argparse.Namespace:
    """Parse command line arguments using modular command parsers."""
    parser = argparse.ArgumentParser(
        prog="netdecker",
        description="Manage Magic The Gathering decklists and proxies",
    )
    parser.formatter_class = argparse.RawDescriptionHelpFormatter

    # Create subparsers for main commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Set up all command parsers from their respective modules
    setup_all_parsers(subparsers)

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> str | None:
    """
    Validate the parsed arguments.
    Returns an error message if validation fails, None otherwise.
    """
    # Check if a command was specified
    if not args.command:
        return "No command specified. Use --help to see available commands."

    # Validate proxy command
    if args.command == "proxy":
        if not args.proxy_command:
            return (
                "No proxy subcommand specified. "
                "Use 'proxy --help' to see available subcommands."
            )

    # Validate deck command
    if args.command == "deck":
        if not args.deck_command:
            return (
                "No deck subcommand specified. "
                "Use 'deck --help' to see available subcommands."
            )

    return None


def route_command(args: argparse.Namespace) -> None:
    """Route parsed arguments to the appropriate command handler."""
    # Initialize database once for all commands
    if not initialize_database():
        LOGGER.error("Failed to initialize database")
        return

    if args.command == "proxy":
        proxy.handle_command(args)
    elif args.command == "deck":
        deck.handle_command(args)
    else:
        LOGGER.error(f"Unknown command: {args.command}")
        LOGGER.error("Use --help to see available commands.")
