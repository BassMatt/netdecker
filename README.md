# NetDecker

NetDecker is a command-line tool for managing Magic: The Gathering decklists and proxy cards. It helps you track your proxy inventory, manage multiple decklists, and generate orders for missing cards.

## Features

- **Proxy Management**: Add, remove, and track proxy card inventory
- **Deck Management**: Import decklists from popular sites (CubeCobra, MTGGoldfish, Moxfield)
- **Smart Allocation**: Automatically allocate cards from inventory to decks
- **Order Generation**: Generate proxy orders in MPCFill format with token support
- **Batch Operations**: Update multiple decks from YAML configuration
- **Preview Mode**: See changes before applying them

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd netdecker

# Install with pip
pip install -e .

# Now you can use the CLI
netdecker --help
```

## Quick Start

```bash
# Add proxy cards to inventory
netdecker proxy add "4 Lightning Bolt" "1 Black Lotus"

# View your inventory
netdecker proxy list

# Add a deck from a URL
netdecker deck add "My Modern Deck" https://www.mtggoldfish.com/deck/123456 --format Modern

# List all tracked decks
netdecker deck list

# Generate an order for missing cards
netdecker deck order --deck "My Modern Deck" --output order.txt
```

## Commands

### Proxy Management

```bash
# Add cards to inventory
netdecker proxy add "4 Lightning Bolt" "2 Counterspell"

# List all proxy cards
netdecker proxy list

# Remove cards from inventory
netdecker proxy remove "1 Lightning Bolt"
```

### Deck Management

```bash
# Add a new deck
netdecker deck add "Deck Name" <url> --format <format>

# List all decks
netdecker deck list

# Show cards in a deck
netdecker deck show "Deck Name"

# Update a deck from its URL
netdecker deck update "Deck Name" [new-url] [--preview]

# Delete a deck
netdecker deck delete "Deck Name" [--confirm]

# Process multiple decks from YAML
netdecker deck batch decks.yaml [--preview] [--order-file output.txt]

# Generate order for missing cards
netdecker deck order --deck "Deck Name" [--output order.txt]
netdecker deck order --url <url> --format <format>
netdecker deck order --yaml decks.yaml
```

## Configuration Files

### Deck Batch YAML Format

```yaml
decklists:
  - format: "Modern"
    decks:
      - name: "Burn"
        url: "https://www.mtggoldfish.com/deck/123456"
      - name: "Control"
        url: "https://www.mtggoldfish.com/deck/789012"

  - format: "Legacy"
    decks:
      - name: "Delver"
        url: "https://www.moxfield.com/decks/abc123"
```

## Supported Deck Sources

- **CubeCobra**: `https://www.cubecobra.com/cube/overview/[cube-id]`
- **MTGGoldfish**: `https://www.mtggoldfish.com/deck/[deck-id]`
- **Moxfield**: `https://www.moxfield.com/decks/[deck-id]`
