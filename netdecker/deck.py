import requests
from urllib.parse import urlparse, quote
import csv
from typing import Optional, Tuple
from main import parse_cardlist
import errors 
from db import SQLiteStore

class DeckSync():
    """
    source_deck_url [Optional]: existing decklist to use for swap information
    dest_deck_url: Deck that you want to order / sync to. Final state.
    proxy_store: Database that holds existing proxy information
    
    """
    def __init__(self, source_deck_url: Optional[str], dest_deck_url: str, proxy_store: SQLiteStore):
        self.dest_deck = self.fetch_decklist(dest_deck_url)
        self.source_deck = self.fetch_decklist(source_deck_url) if source_deck_url else {}
        self.proxy_store = proxy_store


    def fetch_decklist(self, decklist_url: str) -> dict[str, int]:
        """
        Example URLs:

        CubeCobra: https://www.cubecobra.com/cube/overview/MattHomeCube 
        MTGGoldfish: https://www.mtggoldfish.com/deck/6732890#paper
        Moxfield: https://www.moxfield.com/decks/AahWutbE20GeNMt2ENLT7A
        """
        parsed_url = urlparse(decklist_url)
        
        domain = parsed_url.netloc
        deck_id = parsed_url.path.split("/")[-1]
        download_url = ""
        if domain == "www.cubecobra.com":
            download_url = f"https://www.cubecobra.com/cube/download/mtgo/{deck_id}"
        elif domain == "www.mtggoldfish.com":
            download_url = f"https://www.mtggoldfish.com/deck/download/{deck_id}"
        elif domain == "www.moxfield.com":
            resp = requests.get(f"https://api2.moxfield.com/v2/decks/all/{deck_id}")
            if not resp:
                raise errors.UnableToFetchDecklist() 
            resp_json = resp.json()
            if "exportId" in resp_json:
                download_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}/export?format=mtgo&exportId={resp_json['exportId']}"
        else:
            raise errors.DomainNotSupported()
        
        # A GET request to the API
        response = requests.get(download_url)
        response.encoding = response.apparent_encoding

        # cubecobra doesn't properly set content-type header charset
        decklist = {}
        for line in response.text.splitlines():
            if line.startswith("#") or line == "" or not line[0].isdigit(): # skip non-cardlines
                continue
            quantity, card_name = line.strip().split(" ", 1)
            decklist[card_name] += quantity

        decklist = parse_cardlist(response.text.splitlines())

        print(f"Decklist retrieved: {sum(decklist.values())} cards found")

        return decklist
    

    def get_swaps(self) -> Tuple[dict[str, int], dict[str, int]]:
        cards_to_add, cards_to_cut = {}, {}
        for card_name, quantity in self.source_deck.items():
            dest_quantity = self.dest_deck.get(card_name, 0)
            if dest_quantity < quantity:
                pass
        # Generates proxy order for a given
        for card_name, quantity in self.dest_deck.items():
            source_quantity = self.source_deck.get(card_name, 0)
            if quantity > source_quantity:
                cards_to_add[card_name] = quantity - source_quantity
        return (cards_to_add, cards_to_cut)


    def order_proxies(self, cards_to_add: dict[str, int], include_tokens: bool=False) -> Tuple[dict[str, int], dict[str, int]]:
        """
        Generates proxy order 
        
        """
        proxy_order = {}
        token_order = {}
        for card_name, quantity in cards_to_add.items():
            available = 0
            proxy_card = self.proxy_store.get_card(card_name)
            if proxy_card:
                available = proxy_card.available
            if available < quantity:
                proxy_order[card_name] = quantity - available
            
        if include_tokens:
            for card, quantity in proxy_order.items():
                token = self.get_card_tokens(card)
                if token != "":
                    token_order[token] = quantity

        return proxy_order, token_order
    
    
    def save_proxy_order(self, proxy_order: dict[str, int]):
        """
        Updates the proxy store for a given proxy_order.

        Uses any cards that are marked available, and increases the quantity for 
        any cards that needed to be ordered.
        
        """
        for card, quantity in proxy_order.items():
            pass


    def get_card_tokens(self, card):
        url = f"https://api.scryfall.com/cards/named?exact={quote(card)}"
        response = requests.get(url)
        data = response.json()
        if "all_parts" in data:
            for part in data["all_parts"]:
                if part["component"] == "token":
                    return part['name']
        return ""

    def generate_cube_cobra_csv(self, add_cards, remove_cards):
        """
        Utility function to generate a CSV for CubeCobra's 'Replace with CSV File Upload'
        """
        new_cube_list = []
        for card in add_cards:
            new_cube_list.append(card)
        for card in self.child_cube:
            if card not in remove_cards:
                new_cube_list.append(card)

        print(f"Writing new cube list, {len(new_cube_list)} cards")
        still_in_parent = []
        still_in_child = []
        for card in self.parent_cube:
            if card not in new_cube_list:
                still_in_parent.append(card)
        if len(still_in_parent) > 0:
            print(f"Error: found {len(still_in_parent)} cards not added to new cube list in parent")
        for card in new_cube_list:
            if card not in self.parent_cube:
                still_in_child.append(card)
        if len(still_in_child) > 0:
            print(f"Error: found {len(still_in_child)} cards not removed from new cube list")
        
        with open('output/child_cube.csv', 'w') as csvfile:
            # name,CMC,Type,Color,Set,Collector Number,Rarity,Color Category,status,Finish,maybeboard,image URL,image Back URL,tags,Notes,MTGO ID
            fieldnames = ['name', 'CMC', 'Type', 'Color', 'Set', 'Collector Number', 'Rarity', 'Color Category', 'status', 'Finish', 'maybeboard', 'image URL', 'image Back URL', 'tags', 'Notes', 'MTGO ID']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter= ',', quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()
            for card in new_cube_list:
                writer.writerow({'name': card})
    
    def generate_cube_diffs(self):
        """
        Main function for script. Creates several files which represent the
        adds/cuts needed to make to the child cube.
        """
        # Get differences between parent and child cube
        add_cards, remove_cards = self.get_cube_swaps()

        # Creates add cards, remove cards .txt files for making swaps in person
        with open("output/add_cards.txt", "w+") as output:
            for card in add_cards:
                output.write(card + "\n")

        with open("output/remove_cards.txt", "w+") as output:
             for card in remove_cards:
                output.write(card + "\n")

        # Generates CSV to update child cube with swaps
        self.generate_cube_cobra_csv(add_cards, remove_cards)

        # Given cards to add, generates proxy order using existing proxies
        new_cards, proxy_order = self.get_proxy_order(add_cards)
        with open("output/proxy_order.txt", "w+") as output:
            for card in proxy_order:
                output.write(card + "\n")

        with open(self.proxy_list_filename, "w+") as proxy_list:
            new_proxy_list = sorted(self.proxy_list.union(new_cards))
            for card in new_proxy_list:
                proxy_list.write(card + "\n")

