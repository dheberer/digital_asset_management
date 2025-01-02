#!bin/python3
import os

from plex_utils import *
from tmdb_utils import fetch_movie_from_tmdb
from time import sleep
from mutagen.mp4 import MP4, MP4Tags
import datetime

PLEX_LIBRARY_NAME = 'Movies'

# takes name or full path of file and tries to split it
# example: 'Some Cool Movie (2010)' -> {'title': 'Some Cool Movie', 'year':2010}
def _filename_to_movie(filepath: str):
    filename = os.path.basename(filepath)
    title_year = re.compile(r"(.*) \((\d{4})\)")
    if title_year.match(filename):  
        groups = title_year.match(filename).groups()
        return {'title':  groups[0], 'year': int(groups[1]), 'filename': filepath}
    else:
        return {}

def _fetch_mp4_title_year(file_path):
    video = MP4(file_path)

    tags = video.tags or {}
    title = tags.get('\xa9nam', '')
    while isinstance(title, list):
        title = title[0]    
    year = tags.get('\xa9day', '1500')
    while isinstance(year, list):
        year = year[0]       
    return (str(title), str(year))


def _update_mp4_title_year(file_path, new_title, new_year):
    # Load the MP4 file
    try:
        video = MP4(file_path)
    except:
        print(f"Failed to update file {file_path}, tags cause a throw on load.")
        return 
        
    # Access tags
    tags = video.tags
    if tags is None:
        video.add_tags()
        tags = video.tags

    # Update metadata
    tags['\xa9nam'] = str(new_title)  # Title tag
    tags['\xa9day'] = str(new_year)   # Year tag

    # Save changes
    ts = str(datetime.datetime.now())
    video.save()
    print(f"{ts} Updated file '{file_path}' metadata with title '{new_title}' and year '{new_year}.'")

if __name__ == "__main__":

    print(f"{datetime.datetime.now()} Running movie title scanner")
    print('Fetching the movies from the plex server, this could take some time.')
    movies = fetch_movie_infos_from_library(PLEX_LIBRARY_NAME)
    tags_to_do = []
    plex_titles_to_do = []

    for movie in movies:
        sleep(.1)
        tmdb_entry = fetch_movie_from_tmdb(movie['title'], movie['year'])
        if tmdb_entry:
            # If the movie fetch gets something, we just mark it for tag update

            if movie['title'] == tmdb_entry['title'] and movie['year'] == int(tmdb_entry['release_date'][:4]):
                # print(f"[MATCH] -- {movie['title']} ({movie['year']})")
                pass
            else:
                print(f"\n[PLEX] -- {movie['title']} ({movie['year']})")
                print(f"[TMDB] -- {tmdb_entry['title']} ({tmdb_entry['release_date'][:4]})\n")

            # tags_to_do.append({
            #     'title': tmdb_entry['title'],
            #     'year': tmdb_entry['release_date'][:4],
            #     'file_path': movie['filename']
            # })

        else:
            # print(f"\n[FAIL] -- {movie['title']} ({movie['year']}) not matched in TMDB")
            movie_info = _filename_to_movie(movie['filename'])
            if movie_info:
                tmdb_entry = fetch_movie_from_tmdb(movie_info['title'], movie_info['year'])
                if tmdb_entry:
                    # print("[FILE] -- Filename matched a movie in TMDB.")
                    pass
                    # tags_to_do.append({
                    #     'title': tmdb_entry['title'],
                    #     'year': tmdb_entry['release_date'][:4],
                    #     'file_path': movie_info['filename']
                    # })
                    if movie['title'] and movie['year']:
                        # plex_titles_to_do.append({
                        #     'plex_title': movie['title'],
                        #     'plex_year': movie['year']
                        # })
                        pass
                    else:
                        print(f"[PLEX!] -- there is malformed data coming from plex {movie}")
                else:
                    print("!!!"*10)
                    print(f"[FAIL] -- Filename '{movie['filename']}' not matched in TMDB either.\n")
                    # TODO: output the list of misfits somewhere so they can be handled special case

    # fix all tags that don't already match a TMDB entry
    # for ttd in tags_to_do:
    #     tag_title, tag_year = _fetch_mp4_title_year(ttd['file_path'])
    #     if tag_title != ttd['title'] or tag_year != ttd['year']:
    #         print(f"Tags aren't matched on {ttd['file_path']}, setting them...")
    #         _update_mp4_title_year(ttd['file_path'],  ttd['title'], ttd['year'])

    # if the plex movie name or year isn't matching, since we've updated the mp4 tags we can refresh
    # metadata and it will likely fix it.
    # lib = fetch_plex_library(PLEX_LIBRARY_NAME, 'movie')
    # if not lib:
    #     print("Through some kind of magic, no plex library was found.")
    # else:
    #     for pttd in plex_titles_to_do:
    #         movie = fetch_plex_movie(pttd['plex_title'], pttd['plex_year'], lib)
    #         if movie:
    #             movie.refresh()
    #             print(f"Refreshing the metadata for {pttd['plex_title']} ({pttd['plex_year']}).")
    #         else:
    #             print(f"Unable to find {pttd['plex_title']} ({pttd['plex_year']}) in plex.")
