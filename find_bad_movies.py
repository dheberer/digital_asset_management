#!.venv/bin/python
import os
import re
import sys
from tmdb_utils import fetch_movie_from_tmdb

def _filename_to_title_year(filepath: str):
    """
    Splits up the filename into a title and year tuple
    """
    filename = os.path.basename(filepath)
    title_year = re.compile(r"(.*) \((\d{4})\)")
    if title_year.match(filename):  
        groups = title_year.match(filename).groups()
        return (groups[0], int(groups[1]))
    else:
        return (None, None)

def find_mp4_files(directory):
    """
    Find all MP4 files in the given directory and its subdirectories.
    """
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a valid directory")
        sys.exit(1)
    
    # Use os.walk to recursively search through directories
    mp4_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.mp4'):
                mp4_files.append(os.path.join(root, file))
    
    return mp4_files

if __name__ == "__main__":

    # Check if a directory argument was provided
    if len(sys.argv) != 2:
        print("Usage: python find_bad_movies.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    mp4_files = find_mp4_files(directory)
    
    if mp4_files:
        print(f"Found {len(mp4_files)} MP4 files:")
        for file in mp4_files:
            title, year = _filename_to_title_year(file)
            if not title:
                print ('---  ' + file)
                continue

            movie = fetch_movie_from_tmdb(title, year)
            rating = movie.get('vote_average', 0)
            if  rating < 6.2:
                print(str(rating) + '  ' + file)
    else:
        print(f"No MP4 files found in '{directory}'")
