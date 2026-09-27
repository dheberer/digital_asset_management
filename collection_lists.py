"""
Collection name -> list file mapping, shared by the Plex and Jellyfin
collection scripts. Each file in plex_collections/ is tab-separated
"title<TAB>year" lines; lines starting with SEEN are skipped.
"""
import os

COLLECTIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plex_collections')

COLLECTIONS = [
    {'collection_name': '1001 Movies To See Before You Die', 'file_path': os.path.join(COLLECTIONS_DIR, '1001_movies.txt')},
    {'collection_name': 'Best Picture Winners', 'file_path': os.path.join(COLLECTIONS_DIR, 'best_picture_winners.txt')},
    {'collection_name': 'Disney Movies', 'file_path': os.path.join(COLLECTIONS_DIR, 'disney_movies.txt')},
    {'collection_name': 'Best of the Aughts', 'file_path': os.path.join(COLLECTIONS_DIR, 'aughts_100.txt')},
    {'collection_name': 'Best of the Eighties', 'file_path': os.path.join(COLLECTIONS_DIR, '80s_100.txt')},
    {'collection_name': 'Best of the Nineties', 'file_path': os.path.join(COLLECTIONS_DIR, '90s_200.txt')},
    {'collection_name': 'Top Shelf Horror', 'file_path': os.path.join(COLLECTIONS_DIR, 'horror_200.txt')},
    {'collection_name': 'Best of the Twenties', 'file_path': os.path.join(COLLECTIONS_DIR, '20s_best.txt')},
    {'collection_name': 'Timeout Horror 100', 'file_path': os.path.join(COLLECTIONS_DIR, 'timeout_horror_100.txt')},
    {'collection_name': 'A24 Films', 'file_path': os.path.join(COLLECTIONS_DIR, 'a24_films.txt')},
]


def read_collection_file(file_path: str):
    """
    Returns (entries, malformed): entries is a list of (title, year) for
    every non-SEEN line; malformed is the raw lines that weren't
    "title<TAB>year".
    """
    entries, malformed = [], []
    with open(file_path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) != 2:
                malformed.append(line.rstrip('\n'))
                continue
            title, year = parts[0].strip(), parts[1].strip()
            if title.startswith('SEEN'):
                continue
            entries.append((title, year))
    return entries, malformed
