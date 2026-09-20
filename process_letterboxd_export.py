#!.venv/bin/python
"""
Daily Letterboxd -> Plex/Radarr pipeline.

Unpacks the newest manually-downloaded Letterboxd export from the folder
configured as `letterboxd_export_dir` in config.json. If (and only if) a new
export was actually unpacked, syncs the changes out:

- Syncs Letterboxd star ratings to Plex ratings
- Marks every reviewed movie as watched in Plex
- For movies tagged 'deleted' in Letterboxd: marks them SEEN across
  plex_collections/*.txt, then removes them (and their files) from Radarr

Usage:
    python3 process_letterboxd_export.py

    # Unpack into a temp dir (leaving letterboxd_csv/ untouched) and print
    # what would happen, without updating Plex, editing collection files,
    # or removing anything from Radarr
    python3 process_letterboxd_export.py --dry-run
"""

import contextlib
import os
import sys
import tempfile

from config import get_config
from unpack_letterboxd_export import find_latest_export, extract_wanted_files, DEST_DIR
from letterboxd_utils import parse_ratings, parse_reviews, is_deleted, print_review_stats
from plex_utils import fetch_all_plex_movies, sync_ratings_to_plex, mark_reviewed_movies_watched
from radarr_utils import fetch_radarr_movies, remove_movie
from sync_collection_list_from_lb import COLLECTIONS as COLLECTION_FILES, process_collection_file


if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv

    export_dir = get_config('letterboxd_export_dir')
    if not export_dir or not os.path.isdir(export_dir):
        print(f"Export directory not configured or missing: {export_dir}")
        raise SystemExit(1)

    zip_path = find_latest_export(export_dir)
    if not zip_path:
        print(f"No Letterboxd export zip found in {export_dir} -- nothing to do")
        raise SystemExit(0)

    if dry_run:
        print("=== DRY RUN -- unpacking into a temp dir, letterboxd_csv/ will "
              "NOT be overwritten, and no Plex/Radarr/collection file changes "
              "will be made ===\n")

    # Real runs unpack straight into letterboxd_csv/; dry runs unpack into a
    # throwaway temp dir instead, so nothing on disk actually changes.
    dest_dir_ctx = tempfile.TemporaryDirectory() if dry_run else contextlib.nullcontext(DEST_DIR)

    with dest_dir_ctx as dest_dir:
        print(f"Unpacking Letterboxd export: {zip_path}")
        extracted = extract_wanted_files(zip_path, dest_dir)
        if not extracted:
            print("No matching files found in export -- nothing to sync")
            raise SystemExit(0)
        print(f"Extracted: {', '.join(extracted)}")

        lb_ratings = parse_ratings(os.path.join(dest_dir, 'ratings.csv'))
        lb_reviews = parse_reviews(os.path.join(dest_dir, 'reviews.csv'))
        print_review_stats(lb_reviews)

        print("\nFetching Plex library...")
        plex_movies = fetch_all_plex_movies('Movies')
        print(f"Found {len(plex_movies)} movies in Plex")

        print("\nSyncing ratings to Plex...")
        rating_results = sync_ratings_to_plex(plex_movies, lb_ratings, dry_run=dry_run)
        print(f"  Synced: {rating_results['synced']}  "
              f"Already rated: {rating_results['already_rated']}  "
              f"Not in Plex: {rating_results['not_in_plex']}  "
              f"Errors: {rating_results['errors']}")

        print("\nMarking reviewed movies as watched in Plex...")
        watched_results = mark_reviewed_movies_watched(plex_movies, lb_reviews, dry_run=dry_run)
        print(f"  Marked: {watched_results['marked']}  "
              f"Already watched: {watched_results['already_watched']}  "
              f"Not in Plex: {watched_results['not_in_plex']}  "
              f"Errors: {watched_results['errors']}")

        deleted_movies = [
            (review['title'], review['year'])
            for review in lb_reviews.values()
            if is_deleted(review)
        ]
        print(f"\n{len(deleted_movies)} movies tagged 'deleted' in Letterboxd")

        if deleted_movies:
            print("\nMarking deleted movies SEEN across plex_collections/*.txt...")
            for file_path in COLLECTION_FILES:
                if os.path.exists(file_path):
                    process_collection_file(file_path, lb_reviews, plex_movies, dry_run=dry_run)

            print("\nRemoving deleted movies from Radarr (deleting files)...")
            radarr_cache = fetch_radarr_movies(use_cache=False)
            removed, not_in_radarr, failed = 0, 0, 0
            for title, year in deleted_movies:
                success, message = remove_movie(
                    title, year, delete_files=True, movie_cache=radarr_cache, dry_run=dry_run)
                if success:
                    print(f"  {message}")
                    removed += 1
                elif 'NOT IN RADARR' in message:
                    not_in_radarr += 1
                else:
                    print(f"  {message}")
                    failed += 1

            print(f"\n  Removed: {removed}  Not in Radarr: {not_in_radarr}  Failed: {failed}")

    if dry_run:
        print("\n=== DRY RUN complete -- run without --dry-run to apply changes ===")
