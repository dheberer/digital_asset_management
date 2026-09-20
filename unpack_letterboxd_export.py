#!.venv/bin/python
"""
Looks in the folder configured as `letterboxd_export_dir` in config.json for
a Letterboxd data export zip (downloaded manually from
https://letterboxd.com/data/export/), unpacks the most recently downloaded
one, and overwrites ratings.csv and reviews.csv in letterboxd_csv/ so
downstream sync scripts always see the latest export.

Usage:
    python3 unpack_letterboxd_export.py
"""

import glob
import os
import shutil
import sys
import tempfile
import zipfile

from config import get_config

DEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'letterboxd_csv')
WANTED_FILES = ('ratings.csv', 'reviews.csv')


def find_latest_export(export_dir: str):
    """Returns the path to the most recently modified zip file in export_dir, or None."""
    zips = glob.glob(os.path.join(export_dir, '*.zip'))
    if not zips:
        return None
    return max(zips, key=os.path.getmtime)


def extract_wanted_files(zip_path: str, dest_dir: str):
    """
    Extracts ratings.csv and reviews.csv from the export zip (wherever they
    live inside it) into dest_dir, overwriting any existing copies.
    Returns the list of filenames that were extracted.
    """
    extracted = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        for filename in WANTED_FILES:
            matches = glob.glob(os.path.join(tmp_dir, '**', filename), recursive=True)
            if not matches:
                print(f"  WARNING: {filename} not found in export")
                continue
            shutil.copyfile(matches[0], os.path.join(dest_dir, filename))
            extracted.append(filename)

    return extracted


if __name__ == "__main__":
    export_dir = get_config('letterboxd_export_dir')
    if not export_dir:
        print("No 'letterboxd_export_dir' set in config.json")
        sys.exit(1)

    if not os.path.isdir(export_dir):
        print(f"Export directory does not exist: {export_dir}")
        sys.exit(1)

    zip_path = find_latest_export(export_dir)
    if not zip_path:
        print(f"No Letterboxd export zip found in {export_dir}")
        sys.exit(0)

    print(f"Unpacking Letterboxd export: {zip_path}")
    extracted = extract_wanted_files(zip_path, DEST_DIR)

    if extracted:
        print(f"Updated: {', '.join(extracted)}")
    else:
        print("No matching files found in export -- letterboxd_csv/ left unchanged")
