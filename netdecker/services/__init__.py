"""
Service layer for NetDecker.
Provides focused services for different responsibilities:
- CardInventoryService: Manages card inventory (owned/available)
- CardAllocationService: Manages allocation between inventory and decklists
- DecklistService: Manages decklist CRUD operations
"""

from netdecker.db import Session
from netdecker.services.allocation import CardAllocationService
from netdecker.services.card_inventory import CardInventoryService
from netdecker.services.decklist import DecklistService

# Create service instances with the shared session maker
card_inventory_service = CardInventoryService(Session)
card_allocation_service = CardAllocationService(Session)
decklist_service = DecklistService(Session)

# Export for easy importing
__all__ = [
    # Service instances
    "card_inventory_service",
    "card_allocation_service",
    "decklist_service",
    # Service classes
    "CardInventoryService",
    "CardAllocationService",
    "DecklistService",
]
