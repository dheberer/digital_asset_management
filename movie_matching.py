"""
Server-agnostic title/year matching shared by the Plex and Jellyfin utils.

match_movie() only needs objects with .title and .year attributes, so it
works with plexapi Movie objects and jellyfin_utils.JellyfinMovie alike.
"""
import re
import unicodedata


def _normalize_title(title: str) -> str:
    """
    Normalizes a title for fuzzy comparison: unicode-decomposes punctuation
    (an ellipsis character becomes '...', accented letters lose their
    diacritics), then strips everything but letters/digits/spaces and
    collapses whitespace. Lets titles that differ only in punctuation or
    unicode representation (curly quotes, a real ellipsis vs three periods,
    an accent) still compare equal.
    """
    decomposed = unicodedata.normalize('NFKD', title)
    stripped = ''.join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = re.sub(r'[^a-z0-9\s]', ' ', stripped.lower())
    return re.sub(r'\s+', ' ', ascii_only).strip()

def match_movie(title: str, year, plex_movies: dict):
    """
    Matches a (title, year) pair -- typically from a hand-maintained
    collection list -- against a Plex movie cache from
    fetch_all_plex_movies(). Falls back progressively so a stale year or a
    punctuation/unicode difference in the source data doesn't produce a
    false "not found":

    1. 'exact'          -- (title.lower(), year) is a direct cache hit.
    2. 'title_mismatch' -- normalized title matches exactly one movie at
                           the given year, but the raw title text differs
                           (punctuation, unicode, capitalization).
    3. 'year_mismatch'  -- normalized title matches exactly one movie within
                           1 year of the given year (catches festival vs.
                           theatrical release year drift).
    4. 'title_only'     -- normalized title matches exactly one movie in
                           the whole library, at any year. Only used when
                           that match is unambiguous.

    Returns a (movie_or_None, confidence_or_None) tuple.
    """
    target_year = int(year)

    exact = plex_movies.get((title.lower(), target_year))
    if exact:
        return (exact, 'exact')

    normalized_target = _normalize_title(title)
    candidates = [movie for movie in plex_movies.values()
                  if _normalize_title(movie.title) == normalized_target]
    if not candidates:
        return (None, None)

    same_year = [m for m in candidates if m.year == target_year]
    if len(same_year) == 1:
        return (same_year[0], 'title_mismatch')

    within_a_year = [m for m in candidates if abs(m.year - target_year) == 1]
    if len(within_a_year) == 1:
        return (within_a_year[0], 'year_mismatch')

    if len(candidates) == 1:
        return (candidates[0], 'title_only')

    return (None, None)
