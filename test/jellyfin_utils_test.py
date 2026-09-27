"""
Tests for jellyfin_utils against a fake HTTP session (no server needed).

    python3 -m unittest test/jellyfin_utils_test.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import jellyfin_utils as jf  # noqa: E402

USER_ID = 'u1'


class FakeResponse:
    def __init__(self, data):
        self._data = data
        self.content = b'x' if data is not None else b''
        self.headers = {'Content-Type': 'application/json'} if data is not None else {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    """Minimal in-memory Jellyfin: one user, one library, some movies."""

    def __init__(self, movies, boxsets=None, playlists=None):
        self.headers = {}
        self.calls = []
        self.movies = {m['Id']: m for m in movies}
        self.boxsets = boxsets or {}        # id -> {'Name', 'children': [ids]}
        self.playlists = playlists or {}    # id -> {'Name', 'children': [ids]}

    def request(self, method, url, params=None, json=None, timeout=None):
        path = url.split('8096', 1)[1]
        params = params or {}
        self.calls.append((method, path, params, json))

        if path == '/Users':
            return FakeResponse([{'Name': 'Dave', 'Id': USER_ID}])
        if path == '/Library/VirtualFolders':
            return FakeResponse([{'Name': 'Movies', 'ItemId': 'lib1'}])
        if path == '/Items' and method == 'GET':
            t = params.get('includeItemTypes')
            parent = params.get('parentId')
            if t == 'Movie':
                items = list(self.movies.values())
            elif t == 'BoxSet':
                items = [{'Id': k, 'Name': v['Name']} for k, v in self.boxsets.items()]
            elif t == 'Playlist':
                items = [{'Id': k, 'Name': v['Name']} for k, v in self.playlists.items()]
            elif parent in self.boxsets:
                items = [{'Id': i} for i in self.boxsets[parent]['children']]
            else:
                items = []
            start, limit = params['startIndex'], params['limit']
            return FakeResponse({'Items': items[start:start + limit], 'TotalRecordCount': len(items)})
        if path.startswith('/Items/') and method == 'GET':
            return FakeResponse(dict(self.movies[path.split('/')[2]]))
        if path.startswith('/Items/') and method == 'POST':
            self.movies[path.split('/')[2]] = json
            return FakeResponse(None)
        if path == '/Collections' and method == 'POST':
            new_id = f'bs{len(self.boxsets) + 1}'
            self.boxsets[new_id] = {'Name': params['name'], 'children': params['ids'].split(',')}
            return FakeResponse({'Id': new_id})
        if path.startswith('/Collections/'):
            self.boxsets[path.split('/')[2]]['children'] += params['ids'].split(',')
            return FakeResponse(None)
        if path == '/Playlists' and method == 'POST':
            new_id = f'pl{len(self.playlists) + 1}'
            self.playlists[new_id] = {'Name': json['Name'], 'children': list(json['Ids'])}
            return FakeResponse({'Id': new_id})
        if path.startswith('/Playlists/') and method == 'GET':
            ids = self.playlists[path.split('/')[2]]['children']
            return FakeResponse({'Items': [{'Id': i} for i in ids]})
        if path.startswith('/Playlists/') and method == 'POST':
            self.playlists[path.split('/')[2]]['children'] += params['ids'].split(',')
            return FakeResponse(None)
        # user data writes
        return FakeResponse(None)


def movie(id_, name, year, rating=None, played=False, fav=False, tags=None):
    return {'Id': id_, 'Name': name, 'ProductionYear': year, 'Tags': tags or [],
            'UserData': {'Rating': rating, 'Played': played, 'IsFavorite': fav}}


def make_client(session):
    return jf.JellyfinClient('http://jf:8096', 'KEY', 'dave', session=session)


class TestJellyfinUtils(unittest.TestCase):

    def setUp(self):
        self.session = FakeSession([
            movie('m1', 'Alien', 1979, rating=10.0, played=True),
            movie('m2', 'Heat', 1995),
            movie('m3', 'Amélie', 2001),
            movie('m4', 'No Year Movie', None),
        ])
        self.client = make_client(self.session)
        self.movies = jf.fetch_all_jellyfin_movies(self.client, 'Movies')

    def writes(self, prefix):
        return [c for c in self.session.calls if c[0] == 'POST' and c[1].startswith(prefix)]

    def test_auth_header_and_user_lookup(self):
        self.assertIn('Token="KEY"', self.session.headers['Authorization'])
        self.assertEqual(self.client.user_id, USER_ID)

    def test_fetch_keys_by_title_year_and_skips_missing_year(self):
        self.assertEqual(set(self.movies), {('alien', 1979), ('heat', 1995), ('amélie', 2001)})
        self.assertTrue(self.movies[('alien', 1979)].is_watched)

    def test_paging(self):
        jf.PAGE_SIZE, old = 1, jf.PAGE_SIZE
        try:
            self.assertEqual(len(jf.fetch_all_jellyfin_movies(self.client, 'Movies')), 3)
        finally:
            jf.PAGE_SIZE = old

    def test_sync_ratings(self):
        ratings = {('alien', 1979): 5.0, ('heat', 1995): 4.5, ('amelie', 2001): 3.0,
                   ('missing', 2000): 4.0, ('unrated', 2000): None}
        r = jf.sync_ratings_to_jellyfin(self.client, self.movies, ratings, favorite_threshold=4.5)
        self.assertEqual(r, {'synced': 2, 'already_rated': 1, 'favorited': 2,
                             'not_in_jellyfin': 1, 'errors': 0})
        rating_writes = {c[1]: c[3] for c in self.writes('/UserItems/')}
        self.assertEqual(rating_writes['/UserItems/m2/UserData'], {'Rating': 9.0})
        self.assertEqual(rating_writes['/UserItems/m3/UserData'], {'Rating': 6.0})  # fuzzy 'Amelie' match
        self.assertEqual(sorted(c[1] for c in self.writes('/UserFavoriteItems/')),
                         ['/UserFavoriteItems/m1', '/UserFavoriteItems/m2'])
        self.assertTrue(all(c[2]['userId'] == USER_ID for c in self.writes('/User')))

    def test_dry_run_writes_nothing(self):
        jf.sync_ratings_to_jellyfin(self.client, self.movies, {('heat', 1995): 5.0},
                                    favorite_threshold=4.5, dry_run=True)
        jf.mark_reviewed_movies_watched_jellyfin(
            self.client, self.movies, {('heat', 1995): {'title': 'Heat', 'year': 1995}}, dry_run=True)
        jf.add_movies_to_collection(self.client, 'New', list(self.movies.values()), dry_run=True)
        self.assertEqual([c for c in self.session.calls if c[0] == 'POST'], [])

    def test_mark_watched_uses_letterboxd_date(self):
        reviews = {('alien', 1979): {'title': 'Alien', 'year': 1979, 'watched_date': '2024-01-01'},
                   ('heat', 1995): {'title': 'Heat', 'year': 1995, 'watched_date': '2024-03-05'}}
        r = jf.mark_reviewed_movies_watched_jellyfin(self.client, self.movies, reviews)
        self.assertEqual(r['marked'], 1)
        self.assertEqual(r['already_watched'], 1)
        (_, path, params, _), = self.writes('/UserPlayedItems/')
        self.assertEqual(path, '/UserPlayedItems/m2')
        self.assertEqual(params['datePlayed'], '2024-03-05T12:00:00Z')

    def test_tags_are_prefixed_and_merged(self):
        self.session.movies['m2']['Tags'] = ['existing']
        reviews = {('heat', 1995): {'title': 'Heat', 'year': 1995, 'tags': ['keeper', 'theater']}}
        r = jf.sync_tags_to_jellyfin(self.client, self.movies, reviews)
        self.assertEqual(r['tagged'], 1)
        self.assertEqual(self.session.movies['m2']['Tags'], ['existing', 'lb:keeper', 'lb:theater'])
        r = jf.sync_tags_to_jellyfin(self.client, self.movies, reviews)
        self.assertEqual(r['up_to_date'], 1)

    def test_collection_create_then_add_only_missing(self):
        all_movies = list(self.movies.values())
        self.assertEqual(jf.add_movies_to_collection(self.client, 'Faves', all_movies[:1]), 1)
        self.assertEqual(jf.add_movies_to_collection(self.client, 'Faves', all_movies), 2)
        self.assertEqual(jf.add_movies_to_collection(self.client, 'Faves', all_movies), 0)
        (bs,) = self.session.boxsets.values()
        self.assertEqual(sorted(bs['children']), ['m1', 'm2', 'm3'])

    def test_collection_chunks_large_adds(self):
        jf.ID_CHUNK, old = 2, jf.ID_CHUNK
        try:
            jf.add_movies_to_collection(self.client, 'Big', list(self.movies.values()))
        finally:
            jf.ID_CHUNK = old
        self.assertEqual(len(self.writes('/Collections')), 2)

    def test_playlist_create_then_append(self):
        all_movies = list(self.movies.values())
        jf.add_movies_to_playlist(self.client, 'Watchlist', all_movies[:2])
        self.assertEqual(jf.add_movies_to_playlist(self.client, 'Watchlist', all_movies), 1)
        (pl,) = self.session.playlists.values()
        self.assertEqual(pl['children'], ['m1', 'm2', 'm3'])
        create = self.writes('/Playlists')[0]
        self.assertEqual(create[3]['UserId'], USER_ID)
        self.assertEqual(create[3]['MediaType'], 'Video')


if __name__ == '__main__':
    unittest.main()
