#!.venv/bin/python
"""
Goes through collection list files and prepends 'SEEN ' to any movie
that has been reviewed in Letterboxd but is not in the Plex library.

This prevents the collection script from printing those movies as missing
and from adding them to Radarr for download.

Movies are marked SEEN if they appear in your Letterboxd reviews with
tags indicating you watched them elsewhere (deleted, streaming, theater, etc.)
or if they have any review at all.

Usage:
    # Dry run — show what would change without modifying files
    python3 sync_collection_list_from_lb.py --dry-run

    # Apply changes
    python3 sync_collection_list_from_lb.py
"""

import sys
import os
from letterboxd_utils import parse_reviews, get_watch_status, print_review_stats
from plex_utils import fetch_all_plex_movies, match_movie

REVIEWS_PATH = '/media/nas/projects/dam/letterboxd_csv/reviews.csv'

COLLECTIONS = [
    '/media/nas/projects/dam/plex_collections/1001_movies.txt',
    '/media/nas/projects/dam/plex_collections/best_picture_winners.txt',
    '/media/nas/projects/dam/plex_collections/disney_movies.txt',
    '/media/nas/projects/dam/plex_collections/aughts_100.txt',
    '/media/nas/projects/dam/plex_collections/80s_100.txt',
    '/media/nas/projects/dam/plex_collections/90s_200.txt',
    '/media/nas/projects/dam/plex_collections/horror_200.txt',
    '/media/nas/projects/dam/plex_collections/20s_best.txt',
]


def process_collection_file(file_path: str, lb_reviews: dict, plex_movies: dict, dry_run: bool = False):
    """
    Reads a collection file and prepends 'SEEN ' to movies that:
    - Are in Letterboxd reviews (meaning you've watched them)
    - Are NOT in your Plex library (meaning you don't have the file)
    - Are not already marked as SEEN

    Returns counts of changes made.
    """
    filename = os.path.basename(file_path)
    print(f"\nProcessing: {filename}")
    print("-" * 50)

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified_lines = []
    marked = 0
    already_seen = 0
    in_plex = 0
    not_watched = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            modified_lines.append(line)
            continue

        # Already marked as SEEN
        if stripped.startswith('SEEN'):
            already_seen += 1
            modified_lines.append(line)
            continue

        # Parse title and year from tab-separated line
        parts = stripped.split('\t')
        if len(parts) != 2:
            modified_lines.append(line)
            continue

        title = parts[0].strip()
        year_str = parts[1].strip()
        try:
            year = int(year_str)
        except ValueError:
            modified_lines.append(line)
            continue

        # Check if in Plex — if so, leave it alone (collection script handles it)
        movie, confidence = match_movie(title, year, plex_movies)
        if movie:
            if confidence != 'exact':
                print(f"  {confidence.upper()}: '{title}' ({year}) matched Plex's "
                      f"'{movie.title}' ({movie.year})")
            in_plex += 1
            modified_lines.append(line)
            continue

        # Check Letterboxd review status
        status = get_watch_status(title, year, lb_reviews)
        review = lb_reviews.get((title.lower(), year))

        # Mark as SEEN if:
        # - Explicitly tagged (DELETED, SEEN_STREAMING, SEEN_THEATER)
        # - Or rated 2.5 or below (not worth keeping)
        # Do NOT mark if just WATCHED with no tag — needs manual review
        should_mark = False
        if status in ('DELETED', 'SEEN_STREAMING', 'SEEN_THEATER'):
            should_mark = True
        elif review and review.get('rating') is not None and review['rating'] <= 2.5:
            should_mark = True

        if should_mark:
            # Movie was watched — prepend SEEN, keep the tab format
            new_line = f"SEEN {title}\t{year_str}\n"
            modified_lines.append(new_line)
            marked += 1
            rating_str_display = f" (rated {review['rating']})" if review and review.get('rating') else ""
            if not dry_run:
                print(f"  MARKED: {title} ({year}) — {status}{rating_str_display}")
            else:
                print(f"  WOULD MARK: {title} ({year}) — {status}{rating_str_display}")
        else:
            not_watched += 1
            modified_lines.append(line)

    # Write changes if not dry run
    if not dry_run and marked > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)

    print(f"  Summary: {marked} marked, {already_seen} already SEEN, "
          f"{in_plex} in Plex, {not_watched} not watched")

    return {
        'marked': marked,
        'already_seen': already_seen,
        'in_plex': in_plex,
        'not_watched': not_watched
    }


if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=== DRY RUN — no files will be modified ===\n")

    # Load Letterboxd reviews
    print(f"Loading Letterboxd reviews from {REVIEWS_PATH}")
    lb_reviews = parse_reviews(REVIEWS_PATH)
    print_review_stats(lb_reviews)

    # Cache Plex library
    print("\nFetching Plex library...")
    plex_movies = fetch_all_plex_movies('Movies')
    print(f"Found {len(plex_movies)} movies in Plex")

    # Process each collection file
    totals = {'marked': 0, 'already_seen': 0, 'in_plex': 0, 'not_watched': 0}

    for collection_path in COLLECTIONS:
        if not os.path.exists(collection_path):
            print(f"\nSkipping (not found): {collection_path}")
            continue

        results = process_collection_file(collection_path, lb_reviews, plex_movies, dry_run)
        for key in totals:
            totals[key] += results[key]

    # Print grand totals
    print(f"\n{'=' * 50}")
    print(f"Grand Totals:")
    print(f"  Marked as SEEN:  {totals['marked']}")
    print(f"  Already SEEN:    {totals['already_seen']}")
    print(f"  In Plex:         {totals['in_plex']}")
    print(f"  Not watched:     {totals['not_watched']}")

    if dry_run:
        print(f"\n=== DRY RUN — run without --dry-run to apply changes ===")
