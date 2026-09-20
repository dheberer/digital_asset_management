import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append('..')

# plex_utils.py reads tokens.json at import time. Stub one out if it's not
# already there (e.g. a fresh checkout without real credentials) so
# match_movie's pure matching logic can be exercised on its own.
_TOKENS_PATH = os.path.join('..', 'tokens.json')
_created_tokens_file = False
if not os.path.exists(_TOKENS_PATH):
    with open(_TOKENS_PATH, 'w') as f:
        json.dump({'tokens': [{'name': 'plextoken', 'value': 'test'}]}, f)
    _created_tokens_file = True

try:
    from plex_utils import match_movie
finally:
    if _created_tokens_file:
        os.remove(_TOKENS_PATH)


def make_movie(title, year):
    return SimpleNamespace(title=title, year=year)


class TestMatchMovie(unittest.TestCase):

    def setUp(self):
        self.plex_movies = {
            ('ex machina', 2014): make_movie('Ex Machina', 2014),
            ('once upon a time … in hollywood', 2019):
                make_movie('Once Upon a Time … in Hollywood', 2019),
            ('heat', 1995): make_movie('Heat', 1995),
            ('heat', 2019): make_movie('Heat', 2019),
        }

    def test_exact_match(self):
        movie, confidence = match_movie('Heat', 1995, self.plex_movies)
        self.assertEqual(confidence, 'exact')
        self.assertEqual(movie.year, 1995)

    def test_year_off_by_one_falls_back(self):
        # Collection file says 2015, Plex actually has 2014.
        movie, confidence = match_movie('Ex Machina', 2015, self.plex_movies)
        self.assertEqual(confidence, 'year_mismatch')
        self.assertEqual(movie.year, 2014)

    def test_year_off_by_more_than_one_falls_back_to_title_only(self):
        # Still an unambiguous single match on title in the whole library,
        # just too far off-year to call it a year_mismatch.
        movie, confidence = match_movie('Ex Machina', 2018, self.plex_movies)
        self.assertEqual(confidence, 'title_only')
        self.assertEqual(movie.year, 2014)

    def test_ambiguous_title_across_years_is_not_guessed(self):
        # Two different 'Heat' movies in the library -- neither an exact
        # nor an unambiguous fallback match should be made for a bad year.
        movie, confidence = match_movie('Heat', 2000, self.plex_movies)
        self.assertIsNone(movie)
        self.assertIsNone(confidence)

    def test_punctuation_and_unicode_difference_at_right_year(self):
        # Collection file uses three ASCII periods; Plex stored a real
        # ellipsis character. The year is correct, so this should be a
        # title_mismatch, not a year_mismatch.
        movie, confidence = match_movie(
            'Once Upon a Time ... in Hollywood', 2019, self.plex_movies)
        self.assertEqual(confidence, 'title_mismatch')
        self.assertEqual(movie.year, 2019)

    def test_no_match(self):
        movie, confidence = match_movie('Nonexistent Movie', 2020, self.plex_movies)
        self.assertIsNone(movie)
        self.assertIsNone(confidence)


if __name__ == '__main__':
    unittest.main()
