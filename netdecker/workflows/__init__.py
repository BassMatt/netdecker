"""
Workflow layer for NetDecker.
High-level business operations that orchestrate multiple services.
"""

from netdecker.services import (
    card_allocation_service,
    card_inventory_service,
    decklist_service,
)
from netdecker.workflows.deck_management import DeckManagementWorkflow

# Create workflow instances
deck_workflow = DeckManagementWorkflow(
    inventory_service=card_inventory_service,
    allocation_service=card_allocation_service,
    decklist_service=decklist_service,
)

__all__ = [
    "deck_workflow",
    "DeckManagementWorkflow",
]
