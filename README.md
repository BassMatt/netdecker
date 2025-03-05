# NetDecker
This is a script that I use for managing my proxied MagicTheGathering Cube, and set of proxy decks.
The main use case is given a `source` (stranger's) and `dest` (my) decklist, figure out:

1. The cards I need to add to my deck
2. The cards I need to remove from my deck
3. The cards I need to order (and optionally the relevant tokens), given the list of existing proxies

Please use `--help` on the main command, and subcommands to view the available options.

Given an `--output-dir`, the script will spit out some files to help you accomplish that main net-deck "syncing" task.