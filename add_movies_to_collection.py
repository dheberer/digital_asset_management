#!.venv/bin/python
# This script will open a csv file (passed in on cli) that has movie titles and years and then
# add each movie to a collection that matches the name of the file.

from plex_utils import fetch_all_plex_movies, match_movie

if __name__ == "__main__":
    LIB_NAME = 'Movies'
    COLLECTIONS = [
        { 'collection_name': '1001 Movies To See Before You Die', 'file_path': '/media/nas/projects/dam/plex_collections/1001_movies.txt' },
        { 'collection_name': 'Best Picture Winners', 'file_path': '/media/nas/projects/dam/plex_collections/best_picture_winners.txt' },
        { 'collection_name': 'Disney Movies', 'file_path': '/media/nas/projects/dam/plex_collections/disney_movies.txt'},
        { 'collection_name': 'Best of the Aughts', 'file_path': '/media/nas/projects/dam/plex_collections/aughts_100.txt'},
        { 'collection_name': 'Best of the Eighties', 'file_path': '/media/nas/projects/dam/plex_collections/80s_100.txt'},
        { 'collection_name': 'Best of the Nineties', 'file_path': '/media/nas/projects/dam/plex_collections/90s_200.txt'},
        { 'collection_name': 'Top Shelf Horror', 'file_path': '/media/nas/projects/dam/plex_collections/horror_200.txt'},
        { 'collection_name': 'Best of the Twenties', 'file_path': '/media/nas/projects/dam/plex_collections/20s_best.txt'},
        { 'collection_name': 'Timeout Horror 100', 'file_path': '/media/nas/projects/dam/plex_collections/timeout_horror_100.txt'},
        { 'collection_name': 'A24 Films', 'file_path': '/media/nas/projects/dam/plex_collections/a24_films.txt'}  ]
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
