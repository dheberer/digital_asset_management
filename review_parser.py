#!.venv/bin/python
import csv
tags = set()
with open('letterboxd_csv/reviews.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        tag = row.get('Tags', '').strip()
        if tag:
            tags.add(tag)
print('\n'.join(sorted(tags)) if tags else 'No tags found')
