"""
Jellyfin counterpart to plex_utils.py.

Talks to the Jellyfin REST API directly with `requests` (no extra
dependency). Targets Jellyfin 10.10+; the user-data routes used here
(/UserItems, /UserPlayedItems, /UserFavoriteItems) were introduced in 10.9.

Setup
-----
1. In Jellyfin: Dashboard -> API Keys -> "+" and name it "dam".
2. Add it to tokens.json:
       {"tokens": [..., {"name": "jellyfintoken", "value": "<key>"}]}
3. Set `jellyfin_url` and `jellyfin_user` in config.json.

API keys are admin-level and not tied to any user, so every per-user
call (ratings, watched, favorites, playlists) says which user it's for
via `jellyfin_user`.

How Letterboxd data maps onto Jellyfin
--------------------------------------
- Star rating  -> per-user UserData.Rating on a 0-10 scale (stars * 2, same
                  as Plex). Jellyfin stores it and returns it over the API,
                  but the stock web UI doesn't show it -- see README.
- High ratings -> optionally also marked Favorite (the heart), which the UI
                  *does* show and lets you filter on.
- Watched      -> marked Played, with the Letterboxd watched date.
- LB tags      -> optionally written as item Tags (e.g. "lb:keeper"), which
                  you can filter by in the Jellyfin UI. Tags are server-wide
                  metadata, not per-user.
- Collections  -> Jellyfin "BoxSets" (server-wide).
- Playlists    -> per-user playlists.
"""

from dataclasses import dataclass, field
from typing import Optional

import requests

from config import get_config
from movie_matching import match_movie
from tokens import get_token

DEFAULT_URL = 'http://127.0.0.1:8096'
PAGE_SIZE = 500
ID_CHUNK = 100          # keep ?ids=... query strings a sane length
TAG_PREFIX = 'lb:'


@dataclass
class JellyfinMovie:
    """Lightweight stand-in for a plexapi Movie -- enough for match_movie()
    (which needs .title/.year) and the sync functions below."""
    id: str
    title: str
    year: Optional[int]
    rating: Optional[float] = None       # per-user, 0-10
    is_watched: bool = False
    is_favorite: bool = False
    tags: list = field(default_factory=list)
    provider_ids: dict = field(default_factory=dict)
    path: Optional[str] = None

    @classmethod
    def from_item(cls, item: dict) -> 'JellyfinMovie':
        user_data = item.get('UserData') or {}
        return cls(
            id=item['Id'],
            title=item.get('Name', ''),
            year=item.get('ProductionYear'),
            rating=user_data.get('Rating'),
            is_watched=bool(user_data.get('Played')),
            is_favorite=bool(user_data.get('IsFavorite')),
            tags=list(item.get('Tags') or []),
            provider_ids=item.get('ProviderIds') or {},
            path=item.get('Path'),
        )


class JellyfinClient:
    def __init__(self, url: str, api_key: str, user_name: str, session=None):
        self.url = url.rstrip('/')
        self.session = session or requests.Session()
        self.session.headers.update({
            'Authorization': f'MediaBrowser Client="dam", Token="{api_key}"',
            'Accept': 'application/json',
        })
        self.user_name = user_name
        self._user_id = None

    # -- low level ---------------------------------------------------------
    def _request(self, method: str, path: str, params=None, json=None):
        resp = self.session.request(method, f'{self.url}{path}', params=params, json=json, timeout=60)
        resp.raise_for_status()
        if resp.content and 'json' in resp.headers.get('Content-Type', ''):
            return resp.json()
        return None

    def get(self, path, **params):
        return self._request('GET', path, params=params)

    def post(self, path, json=None, **params):
        return self._request('POST', path, params=params, json=json)

    @property
    def user_id(self) -> str:
        if self._user_id is None:
            users = self.get('/Users')
            matches = [u for u in users if u['Name'].lower() == self.user_name.lower()]
            if not matches:
                names = ', '.join(u['Name'] for u in users)
                raise ValueError(f"Jellyfin user '{self.user_name}' not found (have: {names})")
            self._user_id = matches[0]['Id']
        return self._user_id

    def query_items(self, **params) -> list:
        """GET /Items with paging; returns every matching item dict."""
        params.setdefault('recursive', True)
        params.setdefault('userId', self.user_id)
        items, start = [], 0
        while True:
            page = self.get('/Items', startIndex=start, limit=PAGE_SIZE, **params)
            batch = page.get('Items', [])
            items.extend(batch)
            start += len(batch)
            if not batch or start >= page.get('TotalRecordCount', 0):
                return items


def get_client() -> JellyfinClient:
    """Builds a client from config.json + tokens.json."""
    api_key = get_token('jellyfintoken')
    if not api_key:
        raise RuntimeError("No 'jellyfintoken' entry in tokens.json")
    user = get_config('jellyfin_user')
    if not user:
        raise RuntimeError("Set 'jellyfin_user' in config.json")
    return JellyfinClient(get_config('jellyfin_url', DEFAULT_URL), api_key, user)


def _chunks(seq, n=None):
    n = n or ID_CHUNK
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# -- libraries & movies ----------------------------------------------------

def fetch_library_id(client: JellyfinClient, library_name: str) -> Optional[str]:
    for folder in client.get('/Library/VirtualFolders'):
        if folder.get('Name') == library_name:
            return folder.get('ItemId')
    return None


def fetch_all_jellyfin_movies(client: JellyfinClient, library_name: str = 'Movies') -> dict:
    """
    Jellyfin equivalent of plex_utils.fetch_all_plex_movies(): a dict keyed
    by (title_lower, year) whose values are JellyfinMovie objects. Movies
    with no year (unmatched metadata) are skipped.
    """
    library_id = fetch_library_id(client, library_name)
    if not library_id:
        print(f"Jellyfin library '{library_name}' not found")
        return {}

    items = client.query_items(
        parentId=library_id,
        includeItemTypes='Movie',
        fields='ProviderIds,Path,Tags',
        enableUserData=True,
    )
    movies = {}
    for item in items:
        movie = JellyfinMovie.from_item(item)
        if movie.year is None:
            continue
        movies[(movie.title.lower(), movie.year)] = movie
    return movies


def find_movie(title: str, year, jf_movies: dict):
    """Exact (title, year) hit first, then movie_matching's fuzzy fallbacks."""
    movie, _confidence = match_movie(title, year, jf_movies)
    return movie


# -- per-user data ---------------------------------------------------------

def set_rating(client: JellyfinClient, movie: JellyfinMovie, rating: float):
    """Sets the user's 0-10 rating on a movie."""
    client.post(f'/UserItems/{movie.id}/UserData', json={'Rating': rating}, userId=client.user_id)
    movie.rating = rating


def mark_watched(client: JellyfinClient, movie: JellyfinMovie, date_played: str = None):
    """Marks played. date_played is 'YYYY-MM-DD' (Letterboxd's format) or None for now."""
    params = {'userId': client.user_id}
    if date_played:
        params['datePlayed'] = f'{date_played}T12:00:00Z'
    client.post(f'/UserPlayedItems/{movie.id}', **params)
    movie.is_watched = True


def set_favorite(client: JellyfinClient, movie: JellyfinMovie):
    client.post(f'/UserFavoriteItems/{movie.id}', userId=client.user_id)
    movie.is_favorite = True


def add_tags(client: JellyfinClient, movie: JellyfinMovie, tags: list) -> bool:
    """
    Adds tags to a movie's (server-wide) metadata. Jellyfin has no
    "add one tag" endpoint, so this fetches the full item, appends, and
    posts it back. Returns True if anything changed.
    """
    item = client.get(f'/Items/{movie.id}', userId=client.user_id)
    existing = list(item.get('Tags') or [])
    new = [t for t in tags if t not in existing]
    if not new:
        return False
    item['Tags'] = existing + new
    client.post(f'/Items/{movie.id}', json=item)
    movie.tags = item['Tags']
    return True


# -- Letterboxd sync (mirrors plex_utils) ----------------------------------

def sync_ratings_to_jellyfin(client, jf_movies: dict, lb_ratings: dict,
                             favorite_threshold: float = None, dry_run: bool = False) -> dict:
    """
    lb_ratings: {(title_lower, year): stars 0-5} from letterboxd_utils.parse_ratings.
    Sets the Jellyfin rating to stars*2. If favorite_threshold is set (in
    stars, e.g. 4.5), movies rated at or above it are also favorited.
    Returns counts: synced, already_rated, favorited, not_in_jellyfin, errors.
    """
    results = {'synced': 0, 'already_rated': 0, 'favorited': 0, 'not_in_jellyfin': 0, 'errors': 0}

    for (title, year), stars in lb_ratings.items():
        if stars is None:
            continue
        movie = find_movie(title, year, jf_movies)
        if not movie:
            results['not_in_jellyfin'] += 1
            continue

        target = stars * 2
        want_fav = favorite_threshold is not None and stars >= favorite_threshold and not movie.is_favorite
        try:
            if movie.rating == target:
                results['already_rated'] += 1
            elif dry_run:
                print(f"  WOULD RATE: {movie.title} ({movie.year}) -> {stars} stars")
                results['synced'] += 1
            else:
                set_rating(client, movie, target)
                print(f"  Rated: {movie.title} ({movie.year}) -> {stars} stars")
                results['synced'] += 1

            if want_fav:
                if dry_run:
                    print(f"  WOULD FAVORITE: {movie.title} ({movie.year})")
                else:
                    set_favorite(client, movie)
                    print(f"  Favorited: {movie.title} ({movie.year})")
                results['favorited'] += 1
        except Exception as e:
            print(f"  Error rating {movie.title} ({movie.year}): {e}")
            results['errors'] += 1

    return results


def mark_reviewed_movies_watched_jellyfin(client, jf_movies: dict, lb_reviews: dict,
                                          dry_run: bool = False) -> dict:
    """
    Marks every Letterboxd-reviewed movie as played, using the Letterboxd
    watched date as the play date. Returns counts: marked,
    already_watched, not_in_jellyfin, errors.
    """
    results = {'marked': 0, 'already_watched': 0, 'not_in_jellyfin': 0, 'errors': 0}

    for review in lb_reviews.values():
        movie = find_movie(review['title'], review['year'], jf_movies)
        if not movie:
            results['not_in_jellyfin'] += 1
            continue
        if movie.is_watched:
            results['already_watched'] += 1
            continue
        if dry_run:
            print(f"  WOULD MARK WATCHED: {movie.title} ({movie.year}) on {review.get('watched_date') or 'today'}")
            results['marked'] += 1
            continue
        try:
            mark_watched(client, movie, review.get('watched_date') or None)
            print(f"  Marked watched: {movie.title} ({movie.year})")
            results['marked'] += 1
        except Exception as e:
            print(f"  Error marking watched {movie.title} ({movie.year}): {e}")
            results['errors'] += 1

    return results


def sync_tags_to_jellyfin(client, jf_movies: dict, lb_reviews: dict, dry_run: bool = False) -> dict:
    """
    Copies Letterboxd review tags onto the Jellyfin movie as 'lb:<tag>'
    (e.g. lb:keeper, lb:theater) so they're filterable in the Jellyfin UI.
    Returns counts: tagged, up_to_date, not_in_jellyfin, errors.
    """
    results = {'tagged': 0, 'up_to_date': 0, 'not_in_jellyfin': 0, 'errors': 0}

    for review in lb_reviews.values():
        if not review.get('tags'):
            continue
        movie = find_movie(review['title'], review['year'], jf_movies)
        if not movie:
            results['not_in_jellyfin'] += 1
            continue
        wanted = [f'{TAG_PREFIX}{t}' for t in review['tags']]
        missing = [t for t in wanted if t not in movie.tags]
        if not missing:
            results['up_to_date'] += 1
            continue
        if dry_run:
            print(f"  WOULD TAG: {movie.title} ({movie.year}) +{', '.join(missing)}")
            results['tagged'] += 1
            continue
        try:
            add_tags(client, movie, missing)
            print(f"  Tagged: {movie.title} ({movie.year}) +{', '.join(missing)}")
            results['tagged'] += 1
        except Exception as e:
            print(f"  Error tagging {movie.title} ({movie.year}): {e}")
            results['errors'] += 1

    return results


# -- collections (BoxSets) -------------------------------------------------

def fetch_collection(client, collection_name: str) -> Optional[dict]:
    for item in client.query_items(includeItemTypes='BoxSet'):
        if item.get('Name') == collection_name:
            return item
    return None


def fetch_collection_item_ids(client, collection_id: str) -> set:
    return {i['Id'] for i in client.query_items(parentId=collection_id)}


def add_movies_to_collection(client, collection_name: str, movies: list, dry_run: bool = False) -> int:
    """
    Get-or-create a collection and add any of `movies` not already in it,
    in batches. Returns the number of movies added.
    """
    collection = fetch_collection(client, collection_name)
    existing = fetch_collection_item_ids(client, collection['Id']) if collection else set()
    to_add = [m.id for m in movies if m.id not in existing]
    if not to_add:
        return 0
    if dry_run:
        verb = 'add' if collection else 'create with'
        print(f"  WOULD {verb.upper()} {len(to_add)} movies -> '{collection_name}'")
        return len(to_add)

    chunks = list(_chunks(to_add))
    if not collection:
        created = client.post('/Collections', name=collection_name, ids=','.join(chunks[0]))
        collection_id = created['Id']
        chunks = chunks[1:]
    else:
        collection_id = collection['Id']
    for chunk in chunks:
        client.post(f'/Collections/{collection_id}/Items', ids=','.join(chunk))
    return len(to_add)


# -- playlists -------------------------------------------------------------

def fetch_playlist(client, playlist_name: str) -> Optional[dict]:
    for item in client.query_items(includeItemTypes='Playlist'):
        if item.get('Name') == playlist_name:
            return item
    return None


def fetch_playlist_item_ids(client, playlist_id: str) -> list:
    page = client.get(f'/Playlists/{playlist_id}/Items', userId=client.user_id)
    return [i['Id'] for i in page.get('Items', [])]


def add_movies_to_playlist(client, playlist_name: str, movies: list, dry_run: bool = False) -> int:
    """
    Get-or-create one of the user's playlists and append any of `movies`
    not already on it (order preserved). Returns the number added.
    """
    playlist = fetch_playlist(client, playlist_name)
    existing = set(fetch_playlist_item_ids(client, playlist['Id'])) if playlist else set()
    to_add = [m.id for m in movies if m.id not in existing]
    if not to_add:
        return 0
    if dry_run:
        print(f"  WOULD ADD {len(to_add)} movies -> playlist '{playlist_name}'")
        return len(to_add)

    chunks = list(_chunks(to_add))
    if not playlist:
        created = client.post('/Playlists', json={
            'Name': playlist_name, 'Ids': chunks[0],
            'UserId': client.user_id, 'MediaType': 'Video',
        })
        playlist_id = created['Id']
        chunks = chunks[1:]
    else:
        playlist_id = playlist['Id']
    for chunk in chunks:
        client.post(f'/Playlists/{playlist_id}/Items', ids=','.join(chunk), userId=client.user_id)
    return len(to_add)
