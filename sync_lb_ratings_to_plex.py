#!/usr/bin/env python3
"""
Sync Letterboxd ratings to Plex.
Uses the parsed ratings data and caches the Plex library for efficiency
instead of searching per-movie.

Usage:
    python3 sync_lb_ratings_to_plex.py letterboxd_csv/ratings.csv
"""

from plex_utils import fetch_plex_library, fetch_all_plex_movies, rate_movie_in_library
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

    synced = 0
    not_in_plex = 0
    already_rated = 0
    errors = 0

    for (title_lower, year), lb_rating in lb_ratings.items():
        if lb_rating is None:
            continue

        plex_rating = lb_rating * 2  # Letterboxd 0-5 -> Plex 0-10

        # Check if movie is in Plex using cached lookup
        plex_movie = plex_movies.get((title_lower, year))
        if not plex_movie:
            not_in_plex += 1
            continue

        # Check if already rated the same
        if plex_movie.userRating == plex_rating:
            already_rated += 1
            continue

        # Rate the movie
        try:
            plex_movie.rate(plex_rating)
            print(f"  Rated: {plex_movie.title} ({year}) -> {lb_rating} stars")
            synced += 1
        except Exception as e:
            print(f"  Error rating {title_lower} ({year}): {e}")
            errors += 1

    print(f"\nSync complete:")
    print(f"  Synced:        {synced}")
    print(f"  Already rated: {already_rated}")
    print(f"  Not in Plex:   {not_in_plex}")
    print(f"  Errors:        {errors}")
