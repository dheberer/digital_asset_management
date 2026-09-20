#!/usr/bin/env python3
"""
Sync Letterboxd ratings to Plex.
Uses the parsed ratings data and caches the Plex library for efficiency
instead of searching per-movie.

Usage:
    python3 sync_lb_ratings_to_plex.py letterboxd_csv/ratings.csv
"""

from plex_utils import fetch_all_plex_movies, sync_ratings_to_plex
from letterboxd_utils import parse_ratings
import sys


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sync_lb_ratings_to_plex.py <ratings.csv>")
        sys.exit(1)

    ratings_path = sys.argv[1]
    print(f"Parsing ratings from {ratings_path}")
    lb_ratings = parse_ratings(ratings_path)
    print(f"Found {len(lb_ratings)} ratings in Letterboxd export")

    # Cache the entire Plex library once instead of searching per movie
    print("Fetching Plex movie library...")
    plex_movies = fetch_all_plex_movies('Movies')
    print(f"Found {len(plex_movies)} movies in Plex")

    results = sync_ratings_to_plex(plex_movies, lb_ratings)

    print(f"\nSync complete:")
    print(f"  Synced:        {results['synced']}")
    print(f"  Already rated: {results['already_rated']}")
    print(f"  Not in Plex:   {results['not_in_plex']}")
    print(f"  Errors:        {results['errors']}")
