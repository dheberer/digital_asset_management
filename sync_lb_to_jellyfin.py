#!.venv/bin/python
"""
Sync an unpacked Letterboxd export (letterboxd_csv/) to Jellyfin:

- Ratings   -> your Jellyfin rating (stars x 2, 0-10 scale)
- Reviews   -> marked watched, using the Letterboxd watched date
- Favorites -> movies at or above `jellyfin_favorite_threshold` stars
               (config.json) get the heart. Omit the setting to skip.
- --tags     : copy Letterboxd tags onto movies as 'lb:<tag>' so you can
               filter by them in Jellyfin
- --watchlist: mirror your Letterboxd watchlist into a Jellyfin playlist
               called "Letterboxd Watchlist" (only movies you have)

Usage:
    python3 sync_lb_to_jellyfin.py [--dry-run] [--tags] [--watchlist] [csv_dir]
"""

import os
import sys

from config import get_config
from jellyfin_utils import (get_client, fetch_all_jellyfin_movies, find_movie,
                            sync_ratings_to_jellyfin, mark_reviewed_movies_watched_jellyfin,
                            sync_tags_to_jellyfin, add_movies_to_playlist)
from letterboxd_utils import parse_ratings, parse_reviews, parse_watchlist
from unpack_letterboxd_export import DEST_DIR

WATCHLIST_PLAYLIST = 'Letterboxd Watchlist'


def run(csv_dir: str, dry_run=False, tags=False, watchlist=False, jf_movies=None, client=None):
    client = client or get_client()
    if jf_movies is None:
        library = get_config('jellyfin_movie_library', 'Movies')
        print(f"\nFetching Jellyfin library '{library}'...")
        jf_movies = fetch_all_jellyfin_movies(client, library)
        print(f"Found {len(jf_movies)} movies in Jellyfin")

    lb_ratings = parse_ratings(os.path.join(csv_dir, 'ratings.csv'))
    lb_reviews = parse_reviews(os.path.join(csv_dir, 'reviews.csv'))

    print("\nSyncing ratings to Jellyfin...")
    r = sync_ratings_to_jellyfin(client, jf_movies, lb_ratings,
                                 favorite_threshold=get_config('jellyfin_favorite_threshold'),
                                 dry_run=dry_run)
    print(f"  Synced: {r['synced']}  Already rated: {r['already_rated']}  "
          f"Favorited: {r['favorited']}  Not in Jellyfin: {r['not_in_jellyfin']}  Errors: {r['errors']}")

    print("\nMarking reviewed movies as watched in Jellyfin...")
    w = mark_reviewed_movies_watched_jellyfin(client, jf_movies, lb_reviews, dry_run=dry_run)
    print(f"  Marked: {w['marked']}  Already watched: {w['already_watched']}  "
          f"Not in Jellyfin: {w['not_in_jellyfin']}  Errors: {w['errors']}")

    if tags:
        print("\nCopying Letterboxd tags to Jellyfin...")
        t = sync_tags_to_jellyfin(client, jf_movies, lb_reviews, dry_run=dry_run)
        print(f"  Tagged: {t['tagged']}  Up to date: {t['up_to_date']}  "
              f"Not in Jellyfin: {t['not_in_jellyfin']}  Errors: {t['errors']}")

    watchlist_path = os.path.join(csv_dir, 'watchlist.csv')
    if watchlist and os.path.exists(watchlist_path):
        print(f"\nSyncing watchlist to playlist '{WATCHLIST_PLAYLIST}'...")
        wanted = [find_movie(title, year, jf_movies) for title, year in parse_watchlist(watchlist_path)]
        have = [m for m in wanted if m]
        added = add_movies_to_playlist(client, WATCHLIST_PLAYLIST, have, dry_run=dry_run)
        print(f"  {len(have)} of {len(wanted)} watchlist movies are in Jellyfin; {added} newly added")
    elif watchlist:
        print(f"\nNo watchlist.csv in {csv_dir} -- skipping playlist")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    csv_dir = args[0] if args else DEST_DIR
    run(csv_dir,
        dry_run='--dry-run' in sys.argv,
        tags='--tags' in sys.argv,
        watchlist='--watchlist' in sys.argv)
