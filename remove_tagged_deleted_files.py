#!bin/python3
import csv
import os
from plex_utils import fetch_plex_library, fetch_plex_movie

# Look through the reviews and remove any movies from the plex that have this tag on it
with open('reviews.csv', 'r') as file:
    csv_reader = csv.DictReader(file)
    lib = fetch_plex_library('Movies')
    for row in csv_reader:
        if 'deleted' in row['Tags']:
            movie = fetch_plex_movie(row['Name'], int(row['Year']), lib)
            if movie:
                path = movie.media[0].parts[0].file
                if os.path.exists(path):
                    print (f"Removing {path}")
                    os.remove(path)
    