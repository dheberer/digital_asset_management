#!/usr/bin/env python3
import glob
import os
import re
from mutagen.easyid3 import EasyID3
from typing import List


def files_in_dir(path: str) -> List[str]:
    return glob.glob(path + '/**/*.mp3', recursive=True)


def _get_unique_tag(path: str, tag: str) -> str:
    """
    ID3 tags seem to be all returned as lists to us. We get the first item in the list
    I'm sure it will bite me somehow. Also, especially with collaboration I see nested
    lists in the artist tag. so we unroll those.
    """
    info = EasyID3(path)
    value = info.get(tag, None)
    if value is None:
        value = ['Unknown']
    while isinstance(value, list):
        value = value[0]
    return value


def _get_unique_tags(path: str, tag: str) -> List[str]:
    files = files_in_dir(path)
    tags = set()

    for f in files:
        data = _get_unique_tag(f, tag)
        tags.add(data)
    return list(tags)


def clean_album_artist(path: str) -> None:
    """
    gets rid of leading and trailing ['(.*)']
    """
    files = files_in_dir(path)
    for f in files:
        match_info = re.search('^\[\'(.*)\'\]$', _get_unique_tag(f, 'albumartist'))
        if match_info is not None:
            info = EasyID3(f)
            info['albumartist'] = match_info.group(1)
            info.save()


def set_empty_album_artists(path: str) -> None:
    """
    Guess iTunes doesn't set album artist when ripping. This function will look at every
    mp3 file (recursive) in a directory and if it's album artist tag is empty, it sets it.
    """
    files = files_in_dir(path)
    for f in files:
        info = EasyID3(f)
        if info.get('albumartist') is None and info.get('artist') is not None:
            info['albumartist'] = str(info['artist'])
            info.save()


def get_album_artists(path: str) -> List[str]:
    return _get_unique_tags(path, 'albumartist')


def get_file_album_artist(path: str) -> str:
    return _get_unique_tag(path, 'albumartist')


def get_file_album_name(path: str) -> str:
    return _get_unique_tag(path, 'album')


def get_albums(path: str) -> List[str]:
    return _get_unique_tags(path, 'album')


def create_dirs(path: str, dirs: List[str]) -> None:
    pass


def simple_deduplicate(path: str) -> None:
    duplicates = []
    files = files_in_dir(path)
    dup_ending = ' (1).mp3'
    for f in files:
        if f.endswith(dup_ending):
            og = f.replace(dup_ending, '.mp3')
            if og in files:
                duplicates.append(f)
            else:
                os.rename(os.path.join(path, f), os.path.join(path, og))
                print('Renamed ' + f)

    for f in duplicates:
        f = os.path.join(path, f)
        print('Removing ' + f)
        os.remove(f)
