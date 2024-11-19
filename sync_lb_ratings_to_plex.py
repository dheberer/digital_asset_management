from plex_utils import rate_movie_in_library
import csv

def lb_ratings_as_list(filename:str):
    with open('ratings.csv') as csvfile:
        ret_val = []
        reader = csv.DictReader(csvfile)
        return [r for r in reader]


if __name__ == "__main__":
    ratings = lb_ratings_as_list('ratings.csv')
    for r in ratings[:10]:
        if rate_movie_in_library(r['Name'], int(r['Year']), float(r['Rating']) * 2):
            print('***  ' + r['Name'] + '  ' + r['Year'])
        else:
            print('!!!  ' + r['Name'] + '  ' + r['Year'])
