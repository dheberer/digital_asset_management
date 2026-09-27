#!.venv/bin/python
"""
Jellyfin version of add_movies_to_collection.py: builds a Jellyfin
collection for each list in collection_lists.COLLECTIONS, creating the
collection if needed and only adding movies that aren't in it yet.
Movies on a list that aren't in the library are printed.

Usage:
    python3 add_movies_to_jellyfin_collection.py [--dry-run]
"""

import sys

from collection_lists import COLLECTIONS, read_collection_file
from config import get_config
from jellyfin_utils import get_client, fetch_all_jellyfin_movies, add_movies_to_collection
from movie_matching import match_movie


if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv
    library = get_config('jellyfin_movie_library', 'Movies')

    client = get_client()
    print(f"Fetching all movies from the Jellyfin library {library}")
    jf_movies = fetch_all_jellyfin_movies(client, library)
    print(f"Found {len(jf_movies)} movies")

    for c in COLLECTIONS:
        collection_name = c['collection_name']
        print(f"\n{collection_name}\n" + '-' * 30)
        entries, malformed = read_collection_file(c['file_path'])
        for line in malformed:
            print(f"  MALFORMED: {line}")

        matched = []
        for title, year in entries:
            try:
                movie, confidence = match_movie(title, year, jf_movies)
            except ValueError:
                print(f"  BAD YEAR: {title}\t{year}")
                continue
            if not movie:
                print(f"  {title} ({year})")
                continue
            if confidence != 'exact':
                print(f"  {confidence.upper()}: '{title}' ({year}) matched Jellyfin's "
                      f"'{movie.title}' ({movie.year})")
            matched.append(movie)

        added = add_movies_to_collection(client, collection_name, matched, dry_run=dry_run)
        print(f"  {len(matched)} on the list are in Jellyfin; {added} newly added")
