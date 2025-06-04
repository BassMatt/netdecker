import csv
from dataclasses import dataclass, field
from typing import TextIO

from netdecker.config import LOGGER
from netdecker.services.allocation import CardAllocationService
from netdecker.services.card_inventory import CardInventoryService
from netdecker.services.decklist import DecklistService
from netdecker.utils import fetch_decklist, get_card_tokens


@dataclass
class DeckSwaps:
    """Result of comparing two decklists."""

    cards_to_add: dict[str, int] = field(default_factory=dict)
    cards_to_remove: dict[str, int] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        return bool(self.cards_to_add or self.cards_to_remove)


@dataclass
class DeckUpdatePreview:
    """Preview of a deck update operation."""

    deck_name: str
    deck_format: str
    swaps: DeckSwaps = field(default_factory=DeckSwaps)
    cards_to_order: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    info_messages: list[str] = field(default_factory=list)

    @property
    def total_cards_to_order(self) -> int:
        return sum(self.cards_to_order.values())

    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "deck_name": self.deck_name,
            "deck_format": self.deck_format,
            "swaps": {
                "add": self.swaps.cards_to_add,
                "remove": self.swaps.cards_to_remove,
            },
            "cards_to_order": self.cards_to_order,
            "total_cards_to_order": self.total_cards_to_order,
            "errors": self.errors,
            "info_messages": self.info_messages,
        }


@dataclass
class BatchUpdatePreview:
    """Preview of a batch deck update operation."""

    deck_updates: list[DeckUpdatePreview] = field(default_factory=list)

    @property
    def total_order(self) -> dict[str, int]:
        """Aggregate all cards that need to be ordered across all decks."""
        total: dict[str, int] = {}
        for update in self.deck_updates:
            for card, qty in update.cards_to_order.items():
                total[card] = total.get(card, 0) + qty
        return total

    @property
    def total_cards_to_order(self) -> int:
        return sum(self.total_order.values())

    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "deck_updates": [update.to_dict() for update in self.deck_updates],
            "total_order": self.total_order,
            "total_cards_to_order": self.total_cards_to_order,
        }


class DeckManagementWorkflow:
    """
    High-level workflows for deck management with preview/apply pattern.
    """

    def __init__(
        self,
        inventory_service: CardInventoryService,
        allocation_service: CardAllocationService,
        decklist_service: DecklistService,
    ) -> None:
        self.inventory = inventory_service
        self.allocation = allocation_service
        self.decklists = decklist_service

    def preview_deck_update(
        self, url: str, format_name: str, name: str
    ) -> DeckUpdatePreview:
        """
        Preview updating a single deck without making any changes.
        """
        preview = DeckUpdatePreview(deck_name=name, deck_format=format_name)

        try:
            # Fetch the new decklist
            new_cards = fetch_decklist(url)

            # Check if deck exists
            existing_deck = self.decklists.get_decklist(name, format_name)

            if existing_deck:
                # Calculate swaps
                current_cards = self.decklists.get_decklist_cards(existing_deck.id)
                preview.swaps = self._calculate_swaps(current_cards, new_cards)

                # Calculate what we'd need to order (considering what would be freed)
                # Simulate releasing removed cards
                simulated_available = self._simulate_release(
                    preview.swaps.cards_to_remove
                )

                # Check what we'd need for additions
                preview.cards_to_order = self._calculate_order_needs(
                    preview.swaps.cards_to_add, simulated_available
                )
            else:
                # New deck - all cards are additions
                preview.swaps.cards_to_add = new_cards
                preview.cards_to_order = self.allocation.calculate_needed_cards(
                    new_cards
                )

        except Exception as e:
            preview.errors.append(f"Error processing deck: {str(e)}")

        return preview

    def apply_deck_update(
        self, url: str, format_name: str, name: str
    ) -> DeckUpdatePreview:
        """
        Actually apply the deck update (save changes to database).
        """
        # First get the preview
        preview = self.preview_deck_update(url, format_name, name)

        if preview.errors:
            return preview

        try:
            # Fetch the new decklist again
            new_cards = fetch_decklist(url)

            # Check if deck exists
            existing_deck = self.decklists.get_decklist(name, format_name)

            if existing_deck:
                # Release cards from current deck
                self.allocation.release_decklist_allocation(existing_deck.id)

                # Update the decklist
                self.decklists.update_decklist_cards(existing_deck.id, new_cards)
                self.decklists.update_decklist_url(existing_deck.id, url)

                # Allocate cards for the new configuration
                insufficient = self.allocation.allocate_cards(new_cards)
                if insufficient:
                    # Auto-create proxy cards for unallocatable cards
                    self.inventory.add_cards(insufficient)
                    # Try to allocate again after adding proxy cards
                    remaining_insufficient = self.allocation.allocate_cards(
                        insufficient
                    )
                    if remaining_insufficient:
                        total_insufficient = sum(remaining_insufficient.values())
                        preview.errors.append(
                            f"Warning: Could not fully allocate {total_insufficient} cards"
                        )
                    else:
                        total_created = sum(insufficient.values())
                        preview.info_messages.append(
                            f"Info: Created {total_created} proxy cards for allocation"
                        )
            else:
                # Create new deck
                new_deck_id = self.decklists.create_decklist(name, format_name, url)
                self.decklists.update_decklist_cards(new_deck_id, new_cards)

                # Allocate cards
                insufficient = self.allocation.allocate_cards(new_cards)
                if insufficient:
                    # Auto-create proxy cards for unallocatable cards
                    self.inventory.add_cards(insufficient)
                    # Try to allocate again after adding proxy cards
                    remaining_insufficient = self.allocation.allocate_cards(
                        insufficient
                    )
                    if remaining_insufficient:
                        total_insufficient = sum(remaining_insufficient.values())
                        preview.errors.append(
                            f"Warning: Could not fully allocate {total_insufficient} cards"
                        )
                    else:
                        total_created = sum(insufficient.values())
                        preview.info_messages.append(
                            f"Info: Created {total_created} proxy cards for allocation"
                        )

        except Exception as e:
            preview.errors.append(f"Error applying update: {str(e)}")

        return preview

    def preview_batch_update(self, deck_configs: list[dict]) -> BatchUpdatePreview:
        """
        Preview updating multiple decks.
        deck_configs: List of dicts with 'url', 'format', 'name' keys
        """
        batch_preview = BatchUpdatePreview()

        for config in deck_configs:
            deck_preview = self.preview_deck_update(
                config["url"], config["format"], config["name"]
            )
            batch_preview.deck_updates.append(deck_preview)

        return batch_preview

    def apply_batch_update(self, deck_configs: list[dict]) -> BatchUpdatePreview:
        """
        Apply updates to multiple decks.
        """
        batch_preview = BatchUpdatePreview()

        for config in deck_configs:
            deck_preview = self.apply_deck_update(
                config["url"], config["format"], config["name"]
            )
            batch_preview.deck_updates.append(deck_preview)

        return batch_preview

    def write_preview_to_file(
        self,
        preview: DeckUpdatePreview | BatchUpdatePreview,
        file: TextIO,
        save_mode: bool = False,
    ) -> None:
        """Write a preview to a file in a human-readable format."""
        if save_mode:
            if isinstance(preview, DeckUpdatePreview):
                self._write_single_save_summary(preview, file)
            else:
                self._write_batch_save_summary(preview, file)
        else:
            if isinstance(preview, DeckUpdatePreview):
                self._write_single_preview(preview, file)
            else:
                self._write_batch_preview(preview, file)

    def write_order_to_mpcfill(
        self,
        preview: DeckUpdatePreview | BatchUpdatePreview,
        file: TextIO,
        include_tokens: bool = True,
        fetch_tokens: bool = True,
    ) -> None:
        """
        Write order in MPCFill format.

        Args:
            preview: The deck update preview
            file: Output file
            include_tokens: Whether to include generic tokens
            fetch_tokens: Whether to fetch specific tokens from Scryfall
        """
        if isinstance(preview, DeckUpdatePreview):
            cards_to_order = preview.cards_to_order
        else:
            cards_to_order = preview.total_order

        # Write main cards in MTGO format (MPCFill compatible)
        for card_name, quantity in sorted(cards_to_order.items()):
            file.write(f"{quantity} {card_name}\n")

        # Fetch specific tokens from Scryfall if requested
        tokens_to_add = {}
        if fetch_tokens and cards_to_order:
            LOGGER.info("Fetching token information from Scryfall...")
            tokens_to_add = get_card_tokens(list(cards_to_order.keys()))

        if include_tokens or tokens_to_add:
            file.write("\n# Tokens\n")

            # Add fetched tokens
            for token_name, quantity in sorted(tokens_to_add.items()):
                file.write(f"{quantity} {token_name}\n")

            # Add generic tokens if requested and not already included
            if include_tokens:
                generic_tokens = ["Treasure Token", "Beast Token", "Elemental Token"]
                for token in generic_tokens:
                    if token not in tokens_to_add:
                        file.write(f"1 {token}\n")

    def write_cube_csv(self, decklist_id: int, file: TextIO) -> None:
        """
        Generate a CSV file for CubeCobra's 'Replace with CSV File Upload'.
        Used when the deck format is 'Cube'.
        """
        cards = self.decklists.get_decklist_cards(decklist_id)

        # CubeCobra CSV format
        fieldnames = [
            "name",
            "CMC",
            "Type",
            "Color",
            "Set",
            "Collector Number",
            "Rarity",
            "Color Category",
            "status",
            "Finish",
            "maybeboard",
            "image URL",
            "image Back URL",
            "tags",
            "Notes",
            "MTGO ID",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter=",",
            quoting=csv.QUOTE_NONNUMERIC,
        )
        writer.writeheader()

        # Write each card (CubeCobra only needs the name, other fields are optional)
        for card_name, quantity in sorted(cards.items()):
            # For cubes, typically quantity is 1, but write multiple rows if needed
            for _ in range(quantity):
                writer.writerow({"name": card_name})

    def _calculate_swaps(
        self, current_cards: dict[str, int], new_cards: dict[str, int]
    ) -> DeckSwaps:
        """Calculate the differences between two decklists."""
        swaps = DeckSwaps()

        # Normalize card names for comparison (simple lowercase for now)
        current_normalized = {k.lower(): (k, v) for k, v in current_cards.items()}
        new_normalized = {k.lower(): (k, v) for k, v in new_cards.items()}

        # Find additions
        for norm_name, (card_name, new_qty) in new_normalized.items():
            if norm_name in current_normalized:
                _, current_qty = current_normalized[norm_name]
                if new_qty > current_qty:
                    swaps.cards_to_add[card_name] = new_qty - current_qty
            else:
                swaps.cards_to_add[card_name] = new_qty

        # Find removals
        for norm_name, (card_name, current_qty) in current_normalized.items():
            if norm_name in new_normalized:
                _, new_qty = new_normalized[norm_name]
                if current_qty > new_qty:
                    swaps.cards_to_remove[card_name] = current_qty - new_qty
            else:
                swaps.cards_to_remove[card_name] = current_qty

        return swaps

    def _simulate_release(self, cards_to_remove: dict[str, int]) -> dict[str, int]:
        """Simulate releasing cards to see what would be available."""
        simulated = {}

        for card_name, qty in cards_to_remove.items():
            current_available = self.inventory.get_available_quantity(card_name)
            simulated[card_name] = current_available + qty

        return simulated

    def _calculate_order_needs(
        self, cards_to_add: dict[str, int], simulated_available: dict[str, int]
    ) -> dict[str, int]:
        """Calculate what needs to be ordered considering simulated availability."""
        needs = {}

        for card_name, needed_qty in cards_to_add.items():
            available = simulated_available.get(card_name, 0)
            if not available:
                # Check actual current availability
                available = self.inventory.get_available_quantity(card_name)

            if available < needed_qty:
                needs[card_name] = needed_qty - available

        return needs

    def _write_single_save_summary(
        self, preview: DeckUpdatePreview, file: TextIO
    ) -> None:
        """Write a condensed single deck summary for save mode."""
        if preview.errors:
            file.write("ERRORS:\n")
            for error in preview.errors:
                file.write(f"  - {error}\n")
        elif preview.info_messages:
            file.write("INFO:\n")
            for info in preview.info_messages:
                file.write(f"  - {info}\n")

        if preview.swaps.has_changes:
            total_changes = len(preview.swaps.cards_to_add) + len(
                preview.swaps.cards_to_remove
            )
            file.write(
                f"Updated deck '{preview.deck_name}' ({preview.deck_format}) - {total_changes} changes\n"
            )
        else:
            file.write(
                f"No changes needed for deck '{preview.deck_name}' ({preview.deck_format})\n"
            )

        if preview.cards_to_order:
            file.write(f"Need to order {preview.total_cards_to_order} cards\n")
        else:
            file.write("No cards need to be ordered\n")

    def _write_batch_save_summary(
        self, preview: BatchUpdatePreview, file: TextIO
    ) -> None:
        """Write a condensed batch summary for save mode."""
        successful_updates = 0
        error_count = 0

        for deck_update in preview.deck_updates:
            if deck_update.errors:
                error_count += 1
                file.write(
                    f"ERROR - {deck_update.deck_name} ({deck_update.deck_format}): {', '.join(deck_update.errors)}\n"
                )
            else:
                successful_updates += 1
                total_changes = len(deck_update.swaps.cards_to_add) + len(
                    deck_update.swaps.cards_to_remove
                )
                file.write(
                    f"✓ {deck_update.deck_name} ({deck_update.deck_format}) - {total_changes} changes\n"
                )

        file.write(
            f"\nSummary: {successful_updates} successful, {error_count} errors\n"
        )
        if preview.total_order:
            file.write(f"Total cards to order: {preview.total_cards_to_order}\n")

    def _write_single_preview(self, preview: DeckUpdatePreview, file: TextIO) -> None:
        """Write a single deck preview in human-readable format."""
        file.write("=== Deck Update Preview ===\n")
        file.write(f"Deck: {preview.deck_name} ({preview.deck_format})\n\n")

        if preview.errors:
            file.write("ERRORS:\n")
            for error in preview.errors:
                file.write(f"  - {error}\n")
            file.write("\n")

        if preview.info_messages:
            file.write("INFO:\n")
            for info in preview.info_messages:
                file.write(f"  - {info}\n")
            file.write("\n")

        if preview.swaps.cards_to_remove:
            file.write("Cards to Remove:\n")
            for card, qty in sorted(preview.swaps.cards_to_remove.items()):
                file.write(f"  - {qty}x {card}\n")
            file.write("\n")

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
                file.write("Cards to Add (Already Available):\n")
                for card, qty in sorted(cards_available.items()):
                    file.write(f"  + {qty}x {card}\n")
                file.write("\n")

            if cards_to_order:
                file.write("Cards to Add (Ordered):\n")
                for card, qty in sorted(cards_to_order.items()):
                    file.write(f"  + {qty}x {card}\n")
                file.write("\n")

        if preview.cards_to_order:
            file.write(f"Cards to Order ({preview.total_cards_to_order} total):\n")
            for card, qty in sorted(preview.cards_to_order.items()):
                file.write(f"  * {qty}x {card}\n")
        else:
            file.write("No cards need to be ordered!\n")

    def _write_batch_preview(self, preview: BatchUpdatePreview, file: TextIO) -> None:
        """Write a batch preview in human-readable format."""
        file.write("=== Batch Update Preview ===\n")
        file.write(f"Total decks: {len(preview.deck_updates)}\n")
        file.write(f"Total cards to order: {preview.total_cards_to_order}\n\n")

        # Write individual deck updates
        for i, deck_update in enumerate(preview.deck_updates, 1):
            file.write(
                f"--- Deck {i}/{len(preview.deck_updates)}: "
                f"{deck_update.deck_name} ---\n"
            )

            if deck_update.errors:
                file.write("ERRORS: " + ", ".join(deck_update.errors) + "\n")

            if deck_update.swaps.has_changes:
                if deck_update.swaps.cards_to_remove:
                    removals = ", ".join(
                        f"{qty}x {card}"
                        for card, qty in deck_update.swaps.cards_to_remove.items()
                    )
                    file.write(f"Remove: {removals}\n")
                if deck_update.swaps.cards_to_add:
                    additions = ", ".join(
                        f"{qty}x {card}"
                        for card, qty in deck_update.swaps.cards_to_add.items()
                    )
                    file.write(f"Add: {additions}\n")
            else:
                file.write("No changes needed\n")

            if deck_update.cards_to_order:
                orders = ", ".join(
                    f"{qty}x {card}" for card, qty in deck_update.cards_to_order.items()
                )
                file.write(f"Order: {orders}\n")

            file.write("\n")

        # Write total order summary
        if preview.total_order:
            file.write("=== Total Order Summary ===\n")
            for card, qty in sorted(preview.total_order.items()):
                file.write(f"{qty}x {card}\n")
