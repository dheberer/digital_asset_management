#!bin/python3
# This script will open a csv file (passed in on cli) that has movie titles and years and then
# add each movie to a collection that matches the name of the file.

import sys
import os
from mutagen.mp4 import MP4, MP4Tags
from plex_utils import fetch_plex_library, fetch_plex_movie

if __name__ == "__main__":
    LIB_NAME = 'Movies'
    COLLECTIONS = [
        { 'collection_name': '1001 Movies To See Before You Die', 'file_path': '/media/nas/projects/dam/1001_movies.txt' },
        { 'collection_name': 'Best Picture Winners', 'file_path': '/media/nas/projects/dam/best_picture_winners.txt' }
    ]
    print(f"Fetching all movies from the plex library {LIB_NAME}")
    plex_lib = fetch_plex_library(LIB_NAME)

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
                continue
            title = l[0].strip()
            year = l[1].strip()
            movie = fetch_plex_movie(title, year, plex_lib)
            if movie and collection_name not in [c.tag for c in movie.collections]:
                movie.addCollection(collection_name)
            else:
                if not movie:
                    print(f"{title} ({year})")

        print('\n\n')