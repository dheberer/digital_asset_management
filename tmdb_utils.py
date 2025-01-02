from tokens import get_token
from urllib.parse import quote
import requests
import json

TMDB_TOKEN=get_token('tmdbtoken')

def fetch_movie_from_tmdb(title: str, year: int):
    """
    Tries to find a movie with the title provided in tmdb and returns the best match to tile within 2 years of what is passed in.  If a movie
    has a very short title or oft-repeated one this can cause some small troubles, but trying to match exact on year will not return anything if
    the caller is one or two years off (which happens with foreign and older films often)
    """
    if year == None or title == None:
        return {}

    escaped_title = quote(title)
    year = int(year)
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
    best_match = {}
    for movie in results:
        # Sometimes there isn't a release date in the results, we should skip if so.
        try:
            m_year = int(movie.get('release_date', '1000')[:4])
            b_year = int(best_match.get('release_date', '1000')[:4])
            if abs(year - m_year) == 0:
                return movie
            elif (abs(year - m_year) == 1 and abs(year - b_year) > 1) or abs(year - m_year) == 2 and abs(year - b_year) > 2:
                best_match = movie
            else:
                continue

        except:
            continue
 
    return best_match
