import csv
import os


def parse_reviews(reviews_path: str):
    """
    Parses the Letterboxd reviews.csv file.
    Returns a dict keyed by (title_lower, year) with value being a dict
    containing rating, tags, review text, and watched date.
    """
    reviews = {}
    with open(reviews_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Name', '').strip()
            year_str = row.get('Year', '').strip()
            if not title or not year_str:
                continue
            try:
                year = int(year_str)
            except ValueError:
                continue

            tags_raw = row.get('Tags', '').strip()
            tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

            rating_str = row.get('Rating', '').strip()
            try:
                rating = float(rating_str) if rating_str else None
            except ValueError:
                rating = None

            key = (title.lower(), year)
            reviews[key] = {
                'title': title,
                'year': year,
                'rating': rating,
                'tags': tags,
                'review': row.get('Review', '').strip(),
                'watched_date': row.get('Watched Date', '').strip(),
                'rewatch': row.get('Rewatch', '').strip().lower() == 'true',
                'uri': row.get('Letterboxd URI', '').strip(),
            }

    return reviews


def parse_ratings(ratings_path: str):
    """
    Parses the Letterboxd ratings.csv file.
    Returns a dict keyed by (title_lower, year) with value being rating as float.
    """
    ratings = {}
    with open(ratings_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('Name', '').strip()
            year_str = row.get('Year', '').strip()
            rating_str = row.get('Rating', '').strip()
            if not title or not year_str:
                continue
            try:
                year = int(year_str)
                rating = float(rating_str) if rating_str else None
            except ValueError:
                continue

            ratings[(title.lower(), year)] = rating

    return ratings


# Tags that indicate the movie has been watched and should not be downloaded
DELETED_TAGS = {'delete', 'deleted'}
STREAMING_TAGS = {'hbo', 'netflix', 'amazon buy', 'youtube'}
LOCATION_TAGS = {'theater', 'inflight', 'seen_on_a_plane', 'north drive-in'}
SEEN_ELSEWHERE_TAGS = DELETED_TAGS | STREAMING_TAGS | LOCATION_TAGS


def is_watched(review: dict):
    """Returns True if the movie has been watched (any review counts as watched)."""
    return True  # If it's in reviews at all, it's been watched


def is_deleted(review: dict):
    """Returns True if the movie was tagged as deleted."""
    return bool(DELETED_TAGS & set(review.get('tags', [])))


def is_seen_elsewhere(review: dict):
    """Returns True if the movie was seen on streaming, in theater, etc."""
    return bool(SEEN_ELSEWHERE_TAGS & set(review.get('tags', [])))


def should_download(review: dict):
    """
    Returns True if the movie should be downloaded.
    A movie should NOT be downloaded if:
    - It was tagged as deleted
    - It was seen on a streaming service or in theater
    A movie SHOULD be downloaded if:
    - It was tagged as 'keeper'
    - It was reviewed but has no tags suggesting it was seen elsewhere
    """
    tags = set(review.get('tags', []))

    # Explicitly deleted -- never download
    if DELETED_TAGS & tags:
        return False

    # Seen on streaming/theater -- don't download
    if STREAMING_TAGS & tags or LOCATION_TAGS & tags:
        return False

    # Keeper -- definitely download
    if 'keeper' in tags:
        return True

    # Reviewed with no location/service tags -- probably worth having
    return True


def get_watch_status(title: str, year: int, reviews: dict):
    """
    Returns a status string for a movie based on Letterboxd data.
    Possible values: 'DELETED', 'SEEN_STREAMING', 'SEEN_THEATER', 'KEEPER', 'WATCHED', None
    """
    key = (title.lower(), year)
    review = reviews.get(key)

    if not review:
        return None

    tags = set(review.get('tags', []))

    if DELETED_TAGS & tags:
        return 'DELETED'
    if STREAMING_TAGS & tags:
        return 'SEEN_STREAMING'
    if LOCATION_TAGS & tags:
        return 'SEEN_THEATER'
    if 'keeper' in tags:
        return 'KEEPER'

    return 'WATCHED'


def print_review_stats(reviews: dict):
    """Print summary statistics about the reviews."""
    total = len(reviews)
    deleted = sum(1 for r in reviews.values() if is_deleted(r))
    streaming = sum(1 for r in reviews.values() if
                    bool(STREAMING_TAGS & set(r.get('tags', []))))
    theater = sum(1 for r in reviews.values() if
                  bool(LOCATION_TAGS & set(r.get('tags', []))))
    keepers = sum(1 for r in reviews.values() if 'keeper' in r.get('tags', []))
    no_tags = sum(1 for r in reviews.values() if not r.get('tags'))
    rated = sum(1 for r in reviews.values() if r.get('rating') is not None)

    print(f"Letterboxd Review Stats:")
    print(f"  Total reviewed:    {total}")
    print(f"  Rated:             {rated}")
    print(f"  Deleted:           {deleted}")
    print(f"  Streaming:         {streaming}")
    print(f"  Theater/location:  {theater}")
    print(f"  Keepers:           {keepers}")
    print(f"  No tags:           {no_tags}")
