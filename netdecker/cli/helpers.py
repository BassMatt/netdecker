"""Helper functions for CLI commands to reduce duplication."""

from pathlib import Path
from typing import cast

import yaml

from netdecker.config import LOGGER
from netdecker.models.decklist import Decklist
from netdecker.workflows.deck_management import DeckManagementWorkflow


def find_deck(
    name: str,
    format_name: str | None,
    workflow: DeckManagementWorkflow,
    log_error: bool = True,
) -> Decklist | None:
    """Find a deck by name and optional format."""
    if format_name:
        deck = workflow.decklists.get_decklist(name, format_name)
    else:
        deck = workflow.decklists.get_decklist_by_name(name)

    if not deck and log_error:
        # Legacy behavior - only log if explicitly requested
        # Most callers now use CommandResult pattern instead
        LOGGER.error(f"Deck '{name}' not found")

    return deck


def load_yaml_config(yaml_file: str) -> dict[str, object] | None:
    """Load YAML configuration file."""
    yaml_path = Path(yaml_file)
    if not yaml_path.exists():
        # Don't log here - let caller handle via CommandResult
        return None

    with open(yaml_path) as f:
        return yaml.safe_load(f)


def extract_deck_configs(config: dict[str, object]) -> list[dict[str, str]]:
    """Extract deck configurations from YAML config."""
    deck_configs = []
    decklists = cast(list[dict[str, object]], config.get("decklists", []))
    for format_group in decklists:
        format_name = cast(str, format_group.get("format", "Unknown"))
        decks = cast(list[dict[str, object]], format_group.get("decks", []))
        for deck in decks:
            deck_configs.append(
                {
                    "name": cast(str, deck["name"]),
                    "format": format_name,
                    "url": cast(str, deck["url"]),
                }
            )
    return deck_configs
