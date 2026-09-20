import os
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.append('..')
from unpack_letterboxd_export import find_latest_export, extract_wanted_files


class TestUnpackLetterboxdExport(unittest.TestCase):

    def test_find_latest_export_picks_most_recent(self):
        with tempfile.TemporaryDirectory() as export_dir:
            older = os.path.join(export_dir, 'letterboxd-older.zip')
            newer = os.path.join(export_dir, 'letterboxd-newer.zip')
            open(older, 'w').close()
            time.sleep(0.01)
            open(newer, 'w').close()

            self.assertEqual(find_latest_export(export_dir), newer)

    def test_find_latest_export_returns_none_when_empty(self):
        with tempfile.TemporaryDirectory() as export_dir:
            self.assertIsNone(find_latest_export(export_dir))

    def test_extract_wanted_files_overwrites_destination(self):
        with tempfile.TemporaryDirectory() as export_dir, \
                tempfile.TemporaryDirectory() as dest_dir:
            ratings_dest = os.path.join(dest_dir, 'ratings.csv')
            with open(ratings_dest, 'w') as f:
                f.write('stale data')

            zip_path = os.path.join(export_dir, 'letterboxd-export.zip')
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr('ratings.csv', 'Name,Year,Rating\nMovie,2020,4.5\n')
                zf.writestr('reviews.csv', 'Name,Year,Review\nMovie,2020,Great\n')

            extracted = extract_wanted_files(zip_path, dest_dir)

            self.assertEqual(sorted(extracted), ['ratings.csv', 'reviews.csv'])
            with open(ratings_dest) as f:
                self.assertIn('4.5', f.read())

    def test_extract_wanted_files_warns_on_missing_file(self):
        with tempfile.TemporaryDirectory() as export_dir, \
                tempfile.TemporaryDirectory() as dest_dir:
            zip_path = os.path.join(export_dir, 'letterboxd-export.zip')
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr('ratings.csv', 'Name,Year,Rating\nMovie,2020,4.5\n')

            extracted = extract_wanted_files(zip_path, dest_dir)

            self.assertEqual(extracted, ['ratings.csv'])


if __name__ == '__main__':
    unittest.main()
