from plexapi.server import PlexServer
import re
import os
import csv
from tokens import get_token

# Replace these with your Plex server details
PLEX_URL = 'http://127.0.0.1:32400'
PLEX_TOKEN = get_token('plextoken')
        
# You can pass in a string to match library types, pass None if no filter applied
def _fetch_libraries(type_filter:str):
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    if type_filter == None:
        return [l for l in plex.library.sections()]
    else:
        return [l for l in plex.library.sections() if l.type == type_filter]

def _is_collection_in_library(library_name:str, collection_name: str):
    libraries = _fetch_libraries('movie')
    for lib in libraries:
         if library.title == library_name:
            matching_collections = [c for c in lib.collections() if c.title == collection_name]
            return len(matching_collections) > 0
    return False

def fetch_plex_library(library_name: str, library_type:str=None):
    """
    Returns the library object from plex that matches the name passed in.
    """
    libs = _fetch_libraries(library_type)
    for l in libs:
        if l.title == library_name:
            return l
    return None    

def fetch_plex_movie(title: str, year: int, library):
    """
    Returns the movie object from the library that matches the title and year passed in.
    """
    results = library.search(title=str(title), year=int(year))
    if results:
        return results[0]
    else:
        return None

def fetch_movie_infos_from_library(lib_to_fetch: str):
    """
    Returns a list of movies in the library. async call scales with size of library.
    """

    movies = []
    library = fetch_plex_library(lib_to_fetch, 'movie')
    if library:    
        # Library.all() is blocking and can take seconds to complete
        for movie in library.all():
            movies.append({
                'title': movie.title, 
                'year': movie.year, 
                'filename': movie.media[0].parts[0].file})

    return movies

def fetch_duplicated_movies_from_library(lib_to_fetch: str):
    """
    Returns a list of movies in the library. async call scales with size of library.
    """

    movies = []
    library = fetch_plex_library(lib_to_fetch, 'movie')
    if library:    
        # Library.all() is blocking and can take seconds to complete
        for movie in library.all():
            if len(movie.media) > 1 or len(movie.media[0].parts) > 1:
                movies.append({
                    'title': movie.title, 
                    'year': movie.year, 
                    'filename': movie.media[0].parts[0].file})

    return movies    

# Looks for the movie in all movie libraries and rates it. wants a 0-10 scale rating
def rate_movie_in_library(title:str, year:int, rating:float):
    movie_libraries = _fetch_libraries('movie')
    for lib in movie_libraries:
        movie = fetch_plex_movie(title, year, lib)
        if movie:
            movie.rate(rating)
            return True

    return False

def update_movie_title_year_in_library(plex_title: str, plex_year: int, new_title: str = '', new_year: int = 0) -> bool:
    movie_libraries = _fetch_libraries('movie')
    for lib in movie_libraries:
        movie = fetch_plex_movie(plex_title, plex_year, lib) 
        if movie:
            if new_title != '':
                movie.edit(title=new_title)
            if new_year != 0:
                movie.edit(year=new_year)
            if new_title != '' or new_year != 0:
                movie.reload()  # Refresh the movie object to reflect changes
            return True
        else:
            return False

def add_movie_to_collection(plex_movie_title: str, collection_name: str):
    libraries = [l for l in _fetch_libraries('movie') if is_collection_in_library(l.title, collection_name)]
    if libraries:
        l = libraries[0]
        movie = l.get(plex_movie_title)
        if collection_name not in [col.tag for col in movie.collections]:
            movie.addCollection(collection_name)
            
        return True

    return False

# TODO: add review for a movie
