import os
from plex_utils import fetch_movies_from_library, filename_to_movie

# go through all movies and see if the plex title matches the file
if __name__ == "__main__":

    movies = fetch_movies_from_library('Movies')
    for movie in movies:
        if not movie or not movie['filename']:
            print('No filename ' + movie)
            continue
        check = filename_to_movie(movie['filename'])
        if len(check) == 0:
            print(f"Filename malformed: {movie['filename']}")
            continue

        if check['title'].lower() != movie['title'].lower() or check['year'] != movie['year']:
            print("Title or year in plex doesn't match filename")
            print(f"P Title: {movie['title']}\nF Title: {check['title']}")
            print(f"P Year: {movie['year']}\nF Year: {check['year']}\n\n")
    