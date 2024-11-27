from tokens import get_token
from urllib.parse import quote
import requests
import json

TMDB_TOKEN=get_token('tmdbtoken')


def fetch_movie_from_tmdb(title: str, year: int):
    """
    Tries to find a movie with the title provided in tmdb and yerifies the year is within 2 years of what is passed in.
    """
    escaped_title = quote(title)
    url = f"https://api.themoviedb.org/3/search/movie?query={escaped_title}&include_adult=true&language=en-US&page=1"

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_TOKEN}"
    }

    response = requests.get(url, headers=headers)
    if not response.ok:
        return {'error_code': response.status_code}

    # There should be a field named 'results' that holds the matching movies
    d = json.loads(response.text)
    results = d['results']
    for movie in results:
        # Sometimes there isn't a release date in the results, we should skip if so.
        try:
            m_year = int(movie.get('release_date', '1000')[:4])
        except:
            continue
        if abs(year - m_year) < 3:
            return movie
    
    return {}
