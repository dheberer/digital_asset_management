
# This script will open a csv file (passed in on cli) that has movie titles and years and then
# add each movie to a collection that matches the name of the file.

import sys
from mutagen.mp4 import MP4, MP4Tags

print('Adding movies to a collection')
video = MP4('/media/nas/Movies/2010-2019/99 Homes (2014).mp4')
print(video.tags)