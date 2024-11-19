from plexapi.server import PlexServer
import re
import os
import csv
from tokens import get_token

# Replace these with your Plex server details
PLEX_URL = 'http://127.0.0.1:32400'
PLEX_TOKEN = get_token('plextoken')

# takes name or full path of file and tries to split it
# example: 'Some Cool Movie (2010)' -> {'title': 'Some Cool Movie', 'year':2010}
def filename_to_movie(filepath: str):
    filename = os.path.basename(filepath)
    title_year = re.compile(r"(.*) \((\d{4})\)")
    if title_year.match(filename):  
        groups = title_year.match(filename).groups()
        return {'title':  groups[0], 'year': int(groups[1]), 'filename': filepath}
    else:
        return {}
        
# You can pass in a string to match library types, pass None if no filter applied
def fetch_libraries(type_filter:str):
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    if type_filter == None:
        return [l for l in plex.library.sections()]
    else:
        return [l for l in plex.library.sections() if l.type == type_filter]

# Returns a list of movies in the library
def fetch_movies_from_library(lib_to_fetch: str):

    plex = PlexServer(PLEX_URL, PLEX_TOKEN)

    # Access the Movies library
    movies_libraries = fetch_libraries('movie')
    movies = []
    
    for library in movies_libraries:
        if library.title != lib_to_fetch:
            continue

        # Library.all() is blocking and can take seconds to complete
        for movie in library.all():
            movies.append({
                'title': movie.title, 
                'year': movie.year, 
                'filename': movie.media[0].parts[0].file})

    return movies

# Looks for the movie in all movie libraries and rates it. wants a 0-10 scale rating
def rate_movie_in_library(title:str, year:int, rating:float):
    movie_libraries = fetch_libraries('movie')
    for lib in movie_libraries:
        results = lib.search(title=title, year=year)
        if results:
            movie = results[0]
            movie.rate(rating)
            return True

    return False

# TODO: add review for a movie
