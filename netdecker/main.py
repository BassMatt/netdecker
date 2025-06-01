import sys

from .cli.cli import parse_args, route_command, validate_args
from .config import LOGGER


def main() -> int:
    """
    Main entry point for the application.
    Returns exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # Validate arguments
    error = validate_args(args)
    if error:
        LOGGER.error(f"Error: {error}")
        return 1

    # Route to appropriate command handler
    try:
        route_command(args)
        return 0
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1
    except Exception as e:
        LOGGER.error(f"Error executing command: {e}")
        return 1


def cli_main() -> None:
    """Entry point for the CLI."""
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
