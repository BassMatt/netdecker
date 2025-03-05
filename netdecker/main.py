import argparse
import db
from collections import Counter
from errors import CardListInputError
def process_cmdline():
    parser = argparse.ArgumentParser(
        prog="NetDecker",
        description="Helps with ordering changes for cubes / decklists!"
    )
    sub_parsers = parser.add_subparsers(dest="command")

    sync_parser = sub_parsers.add_parser("sync", help="sync two decklists")
    sync_parser.add_argument('--source-url', default="MattHomeCube", help="existing decklist, if exists")
    sync_parser.add_argument('--dest-url', default="LSVCube", help="list to sync to, final state")
    sync_parser.add_argument('--output-dir', default="./output", help="")


    proxy_parser = sub_parsers.add_parser("proxy", help="commands to help manage proxy list")
    proxy_sub_parser = proxy_parser.add_subparsers(dest="proxy_command")

    proxy_import_parser = proxy_sub_parser.add_parser("import", help="import existing proxylist to netdecker collection")
    proxy_import_parser.add_argument("--local-list", help="filepath of .txt in MTGO format")
    proxy_import_parser.add_argument("--remote-list", help="URL of moxfield/mtggoldfish decklist to import")

    proxy_list_parser = proxy_sub_parser.add_parser("list", help="list the existing proxylist/collection")
    proxy_list_parser.add_argument("--output", "-o")

    proxy_sub_parser.add_parser("free", help="make proxies in supplied list available for use")
    proxy_import_parser.add_argument("--local-list", help="filepath of .txt in MTGO format")
    proxy_import_parser.add_argument("--remote-list", help="URL of moxfield/mtggoldfish decklist to import")

    return parser.parse_args()

def read_cardlist_from_file(path: str):
    with open(path) as f:
        return f.readlines()
    
def parse_cardlist(card_list: list[str]) -> dict[str, int]:
    """
    Parses and validates provided cardlist is in MTGO format and contains valid cardnames.

    Returns: Dictionary that maps CardName -> Count 
    """
    line_errors = []
    cards = Counter()
    for line in card_list:
        if line.startswith("#") or line == "" or not line[0].isdigit():
            # skip non-cardlines
            continue

        split = line.strip().split(" ", 1)

        if len(split) != 2:
            line_errors.append(line)
            continue

        if not split[0].isdigit():
            line_errors.append(line)
            continue
        
        quantity, card_name = int(split[0]), split[1]

        cards[card_name] += quantity
    
    if len(line_errors) > 0:
        raise CardListInputError(line_errors)
    else:
        return cards

if __name__ == "__main__":
    args = process_cmdline()
    proxy_store = db.SQLiteStore("sqlite:///./proxy.db") 

    if args.command == "cube":
        pass
    elif args.command == "proxy":
        if args.proxy_command == "import":
            if args.local_list:
                card_list = parse_cardlist(read_cardlist_from_file(args.local_list))
                proxy_store.add_cards(card_list)
            elif args.remote_list:
                #TODO: import from remote .txt.
                pass
        elif args.proxy_command == "list":
            cards = proxy_store.get_cards()
            for card in cards:
                print(f"{card.quantity} {card.name}")