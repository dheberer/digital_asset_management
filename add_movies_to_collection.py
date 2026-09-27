#!.venv/bin/python
# This script will open a csv file (passed in on cli) that has movie titles and years and then
# add each movie to a collection that matches the name of the file.

from plex_utils import fetch_all_plex_movies, match_movie
from collection_lists import COLLECTIONS

LIB_NAME = 'Movies'

if __name__ == "__main__":
    print(f"Fetching all movies from the plex library {LIB_NAME}")
    plex_movies = fetch_all_plex_movies(LIB_NAME)

    for c in COLLECTIONS:
        file_path = c['file_path']
        collection_name = c['collection_name']
        print(f"Loading the movies to add to the collection {collection_name}")
        with open(file_path) as movie_file:
            lines = [l.split('\t') for l in movie_file]
        print('-'*30)

        # should be a list with title and string as it's two members
        for l in lines:
            if len(l) != 2:
                print('\t'.join(l))
                continue
            title = l[0].strip()
            year = l[1].strip()
            if title.startswith('SEEN'):
                continue

            try:
                movie, confidence = match_movie(title, year, plex_movies)
                if movie:
                    if confidence != 'exact':
                        print(f"  {confidence.upper()}: '{title}' ({year}) matched Plex's "
                              f"'{movie.title}' ({movie.year})")
                    if collection_name not in [col.tag for col in movie.collections]:
                        movie.addCollection(collection_name)
                else:
                    print(f"{title} ({year})")

            except Exception as e:
                print(f"Error {e} thrown on {l}")
        print('\n\n')
