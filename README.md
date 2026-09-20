# digital_asset_management
scripts to automate managing movies, music, pictures among various services

This is not for real public consumption, but looking in the utils files might give you a nudge in how you can write your own scripts to help manage your media

## Configuration

Repo-wide settings that aren't secrets (unlike `tokens.json`) live in `config.json` at the repo root. Edit it in place rather than passing it around:

```json
{
    "letterboxd_export_dir": "/media/nas/projects/dam/letterboxd_export"
}
```

- `letterboxd_export_dir` — folder to manually drop your downloaded Letterboxd data export zip (from https://letterboxd.com/data/export/) into. `unpack_letterboxd_export.py` reads from here.

## Automation

Scripts intended to run on a schedule (via cron):

```
# Unpack the latest manually-downloaded Letterboxd export into letterboxd_csv/
0 2 * * * /media/nas/projects/dam/.venv/bin/python3 /media/nas/projects/dam/unpack_letterboxd_export.py

# Add movies to Plex collections based on plex_collections/*.txt
30 2 * * * /media/nas/projects/dam/.venv/bin/python3 /media/nas/projects/dam/add_movies_to_collection.py
```

`unpack_letterboxd_export.py` is a no-op (exit 0) if the export folder has no zip in it yet, so it's safe to run daily even between manual downloads.
