from tokens import get_token
import requests
import time

RADARR_URL = 'http://localhost:7878'
RADARR_API_KEY = get_token('radarrtoken')

HEADERS = {
    'X-Api-Key': RADARR_API_KEY,
    'Content-Type': 'application/json'
}

# Module-level cache for Radarr movies and quality profiles
_radarr_movie_cache = None
_quality_profile_cache = None


def fetch_radarr_movies(use_cache: bool = True):
    """
    Returns a list of all movies currently in Radarr's database.
    Caches the result for subsequent calls unless use_cache is False.
    """
    global _radarr_movie_cache
    if use_cache and _radarr_movie_cache is not None:
        return _radarr_movie_cache

    response = requests.get(f"{RADARR_URL}/api/v3/movie", headers=HEADERS)
    response.raise_for_status()
    _radarr_movie_cache = response.json()
    return _radarr_movie_cache


def invalidate_cache():
    """Clear the cached movie list so the next call fetches fresh data."""
    global _radarr_movie_cache
    _radarr_movie_cache = None


def is_movie_in_radarr(title: str, year: int = None, movie_cache: list = None):
    """
    Checks if a movie is already in Radarr's database.
    Accepts an optional movie_cache list to avoid repeated API calls.
    Also checks alternative titles for foreign film matching.
    Returns the movie dict if found, None otherwise.
    """
    movies = movie_cache if movie_cache is not None else fetch_radarr_movies()
    title_lower = title.lower().strip()

    for movie in movies:
        # Check primary title
        if movie.get('title', '').lower() == title_lower:
            if year is None or movie.get('year') == int(year):
                return movie

        # Check original title (useful for foreign films)
        if movie.get('originalTitle', '').lower() == title_lower:
            if year is None or movie.get('year') == int(year):
                return movie

        # Check alternative titles
        for alt in movie.get('alternateTitles', []):
            if alt.get('title', '').lower() == title_lower:
                if year is None or movie.get('year') == int(year):
                    return movie

    return None


def lookup_movie(title: str, year: int = None):
    """
    Searches Radarr's movie lookup (which queries TMDB) for a movie.
    Returns a tuple of (best_match, confidence) where confidence is one of:
    'exact', 'year_match', 'fuzzy', or None if not found.
    """
    search_term = f"{title} {year}" if year else title
    response = requests.get(
        f"{RADARR_URL}/api/v3/movie/lookup",
        headers=HEADERS,
        params={'term': search_term}
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        return (None, None)

    title_lower = title.lower().strip()

    # Best case: exact title and year match
    if year:
        for result in results:
            result_title = result.get('title', '').lower()
            result_original = result.get('originalTitle', '').lower()
            result_year = result.get('year')

            if result_year == int(year):
                if result_title == title_lower or result_original == title_lower:
                    return (result, 'exact')

        # Check alternative titles for exact match with year
        for result in results:
            if result.get('year') == int(year):
                for alt in result.get('alternateTitles', []):
                    if alt.get('title', '').lower() == title_lower:
                        return (result, 'exact')

        # Year matches but title doesn't match exactly
        for result in results:
            if result.get('year') == int(year):
                return (result, 'year_match')

    # Fallback: return first result as a fuzzy match
    return (results[0], 'fuzzy')


def fetch_quality_profiles():
    """
    Returns a list of quality profiles configured in Radarr.
    Caches the result for subsequent calls.
    """
    global _quality_profile_cache
    if _quality_profile_cache is not None:
        return _quality_profile_cache

    response = requests.get(f"{RADARR_URL}/api/v3/qualityprofile", headers=HEADERS)
    response.raise_for_status()
    _quality_profile_cache = response.json()
    return _quality_profile_cache


def get_quality_profile_id(profile_name: str):
    """
    Returns the ID of a quality profile by name, or None if not found.
    """
    profiles = fetch_quality_profiles()
    for profile in profiles:
        if profile.get('name', '').lower() == profile_name.lower():
            return profile['id']
    return None


def add_movie(title: str, year: int, root_folder: str = '/media/nas2/Movies',
              quality_profile: str = 'HD - 720p/1080p', monitored: bool = True,
              search: bool = True, movie_cache: list = None):
    """
    Looks up a movie and adds it to Radarr if not already present.
    Returns a tuple of (success: bool, message: str).
    
    Possible outcomes:
    - Already in Radarr
    - Not found in TMDB
    - Added with exact match
    - Added with fuzzy match (title may differ - check message)
    - Failed to add
    """
    # Check if already in Radarr
    existing = is_movie_in_radarr(title, year, movie_cache)
    if existing:
        return (True, f"Already in Radarr: {existing['title']} ({existing.get('year')})")

    # Look up the movie on TMDB via Radarr
    lookup, confidence = lookup_movie(title, year)
    if not lookup:
        return (False, f"NOT FOUND: {title} ({year})")

    # Warn if the match is not exact
    matched_title = lookup.get('title', '')
    matched_year = lookup.get('year', '')
    match_info = ""
    if confidence == 'fuzzy':
        match_info = f" [FUZZY MATCH: found '{matched_title} ({matched_year})']"
    elif confidence == 'year_match':
        match_info = f" [YEAR MATCH: found '{matched_title} ({matched_year})']"

    # Get quality profile ID
    profile_id = get_quality_profile_id(quality_profile)
    if not profile_id:
        return (False, f"Quality profile not found: {quality_profile}")

    # Build the movie payload
    payload = {
        'tmdbId': lookup['tmdbId'],
        'title': lookup['title'],
        'year': lookup.get('year', year),
        'qualityProfileId': profile_id,
        'rootFolderPath': root_folder,
        'monitored': monitored,
        'addOptions': {
            'searchForMovie': search
        }
    }

    response = requests.post(f"{RADARR_URL}/api/v3/movie", headers=HEADERS, json=payload)

    if response.status_code == 201:
        invalidate_cache()
        return (True, f"Added: {matched_title} ({matched_year}){match_info}")
    elif response.status_code in [400, 503]:
        time.sleep(5)
        error = response.json()
        msg = error[0].get('errorMessage', str(error)) if isinstance(error, list) else str(error)
        return (False, f"Failed to add {title} ({year}): {msg}")
    else:
        response.raise_for_status()
        return (False, f"Unexpected response: {response.status_code}")


def remove_movie(title: str, year: int, delete_files: bool = True, movie_cache: list = None):
    """
    Removes a movie from Radarr by title/year, optionally deleting its files
    from disk as well.
    Returns a tuple of (success: bool, message: str).
    """
    existing = is_movie_in_radarr(title, year, movie_cache)
    if not existing:
        return (False, f"NOT IN RADARR: {title} ({year})")

    response = requests.delete(
        f"{RADARR_URL}/api/v3/movie/{existing['id']}",
        headers=HEADERS,
        params={'deleteFiles': str(delete_files).lower(), 'addImportExclusion': 'false'}
    )

    if response.status_code == 200:
        invalidate_cache()
        return (True, f"Removed: {existing['title']} ({existing.get('year')})")
    else:
        return (False, f"Failed to remove {title} ({year}): {response.status_code} {response.text}")


def process_movie_list(movie_list: list, root_folder: str = '/media/nas2/Movies',
                       quality_profile: str = 'HD - 720p/1080p', search: bool = True):
    """
    Processes a list of (title, year) tuples. Adds missing movies to Radarr.
    Returns a dict with 'added', 'existing', 'not_found', and 'fuzzy' lists.

    Usage:
        movies = [('Blade Runner', 1982), ('Spirited Away', 2001)]
        results = process_movie_list(movies)
        for title, year, msg in results['not_found']:
            print(f"Could not find: {title} ({year})")
    """
    results = {
        'added': [],
        'existing': [],
        'not_found': [],
        'fuzzy': [],
        'failed': []
    }

    # Pre-fetch and cache the movie list
    movie_cache = fetch_radarr_movies(use_cache=False)

    for title, year in movie_list:
        print(f"Attempting to add {title} {year} to radarrr")
        success, message = add_movie(
            title, int(year),
            root_folder=root_folder,
            quality_profile=quality_profile,
            search=search,
            movie_cache=movie_cache
        )

        time.sleep(1)
        if not success:
            if 'NOT FOUND' in message:
                results['not_found'].append((title, year, message))
            else:
                results['failed'].append((title, year, message))
        elif 'Already in Radarr' in message:
            results['existing'].append((title, year, message))
        elif 'FUZZY MATCH' in message or 'YEAR MATCH' in message:
            results['fuzzy'].append((title, year, message))
            movie_cache = fetch_radarr_movies(use_cache=False)
        else:
            results['added'].append((title, year, message))
            movie_cache = fetch_radarr_movies(use_cache=False)

    return results


def print_results(results: dict, collection_name: str = ''):
    """Pretty print the results from process_movie_list."""
    header = f" Results for {collection_name} " if collection_name else " Results "
    print(f"\n{'=' * 60}")
    print(f"{header:=^60}")
    print(f"{'=' * 60}")

    print(f"\n  Added:    {len(results['added'])}")
    print(f"  Existing: {len(results['existing'])}")
    print(f"  Fuzzy:    {len(results['fuzzy'])}")
    print(f"  Missing:  {len(results['not_found'])}")
    print(f"  Failed:   {len(results['failed'])}")

    if results['fuzzy']:
        print(f"\n--- Fuzzy/uncertain matches (verify these) ---")
        for title, year, msg in results['fuzzy']:
            print(f"  {title} ({year}): {msg}")

    if results['not_found']:
        print(f"\n--- Not found in TMDB (check spelling/year) ---")
        for title, year, msg in results['not_found']:
            print(f"  {title} ({year})")

    if results['failed']:
        print(f"\n--- Failed to add ---")
        for title, year, msg in results['failed']:
            print(f"  {title} ({year}): {msg}")

    print()
