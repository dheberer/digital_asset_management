#!.venv/bin/python
"""
Goes through collection lists, finds movies that are:
- Not in Plex
- Not marked as SEEN
- Not already in Radarr

And adds them to Radarr for monitoring and download.

Usage:
    # Dry run — show what would be added without doing anything
    python3 radarr_missing_from_collection.py --dry-run

    # Add missing movies to Radarr
    python3 radarr_missing_from_collection.py
"""

import sys
from plex_utils import fetch_all_plex_movies, match_movie
from radarr_utils import process_movie_list, print_results

COLLECTIONS = [
#    { 'collection_name': 'Best Picture Winners', 'file_path': '/media/nas/projects/dam/plex_collections/best_picture_winners.txt' },
    { 'collection_name': 'Best of the Aughts', 'file_path': '/media/nas/projects/dam/plex_collections/aughts_100.txt'},
    { 'collection_name': 'Best of the Eighties', 'file_path': '/media/nas/projects/dam/plex_collections/80s_100.txt'},
    { 'collection_name': 'Best of the Nineties', 'file_path': '/media/nas/projects/dam/plex_collections/90s_200.txt'},
#    { 'collection_name': 'Top Shelf Horror', 'file_path': '/media/nas/projects/dam/plex_collections/horror_200.txt'},
    { 'collection_name': 'Best of the Twenties', 'file_path': '/media/nas/projects/dam/plex_collections/20s_best.txt'},
#    { 'collection_name': '1001 Movies To See Before You Die', 'file_path': '/media/nas/projects/dam/plex_collections/1001_movies.txt' },
#    { 'collection_name': 'Disney Movies', 'file_path': '/media/nas/projects/dam/plex_collections/disney_movies.txt'},
#    { 'collection_name': 'Timeout Horror 100', 'file_path': '/media/nas/projects/dam/plex_collections/timeout_horror_100.txt'},
    {'collection_name': 'A24 Films', 'file_path': '/media/nas/projects/dam/plex_collections/a24_films.txt'}
]


if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=== DRY RUN — nothing will be added to Radarr ===\n")

    # Cache Plex library once
    print("Fetching Plex library...")
    plex_movies = fetch_all_plex_movies('Movies')
    print(f"Found {len(plex_movies)} movies in Plex\n")

    for c in COLLECTIONS:
        file_path = c['file_path']
        collection_name = c['collection_name']
        print(f"Processing: {collection_name}")
        print("-" * 50)

        try:
            with open(file_path) as movie_file:
                lines = [l.split('\t') for l in movie_file]
        except FileNotFoundError:
            print(f"  File not found: {file_path}\n")
            continue

        missing_movies = []

        for l in lines:
            if len(l) != 2:
                continue

            title = l[0].strip()
            year = l[1].strip()

            # Skip movies already marked as SEEN
            if title.startswith('SEEN'):
                continue

            # Skip movies already in Plex
            try:
                year_int = int(year)
            except ValueError:
                continue

            movie, confidence = match_movie(title, year_int, plex_movies)
            if movie:
                if confidence != 'exact':
                    print(f"  {confidence.upper()}: '{title}' ({year}) matched Plex's "
                          f"'{movie.title}' ({movie.year}) -- not adding to Radarr")
                continue

            missing_movies.append((title, year_int))

        print(f"  Found {len(missing_movies)} movies not in Plex")

        if missing_movies:
            if dry_run:
                print(f"  Would add to Radarr:")
                for title, year in missing_movies:
                    print(f"    {title} ({year})")
            else:
                results = process_movie_list(missing_movies, search=True)
                print_results(results, collection_name)

        print()

    if dry_run:
        print("=== DRY RUN — run without --dry-run to add movies to Radarr ===")
