# digital_asset_management
scripts to automate managing movies, music, pictures among various services

This is not for real public consumption, but looking in the utils files might give you a nudge in how you can write your own scripts to help manage your media

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

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
# Unpack the latest manually-downloaded Letterboxd export and, if one was
# found, sync ratings/watched status to Plex and remove deleted-tagged
# movies from Radarr
0 2 * * * /media/nas/projects/dam/.venv/bin/python3 /media/nas/projects/dam/process_letterboxd_export.py

# Add movies to Plex collections based on plex_collections/*.txt
30 2 * * * /media/nas/projects/dam/.venv/bin/python3 /media/nas/projects/dam/add_movies_to_collection.py
```

`process_letterboxd_export.py` is a no-op (exit 0) if the export folder has no zip in it yet. When it does find one, it unpacks it into `letterboxd_csv/` (overwriting the previous export) and then:

- Syncs Letterboxd star ratings to Plex ratings
- Marks every reviewed movie as watched in Plex
- For movies tagged `deleted` in Letterboxd: marks them `SEEN` across `plex_collections/*.txt` and removes them, files included, from Radarr

`unpack_letterboxd_export.py` still works standalone if you just want the CSV refresh without the sync/removal steps.

Run with `--dry-run` to preview a pipeline run: the export is unpacked into a temp directory (leaving `letterboxd_csv/` untouched) and every step prints what it would do instead of updating Plex, editing collection files, or calling Radarr.

```
.venv/bin/python3 process_letterboxd_export.py --dry-run
```

## Jellyfin

`jellyfin_utils.py` is the Jellyfin counterpart to `plex_utils.py`. It uses the Jellyfin REST API directly through `requests` and needs Jellyfin 10.10 or newer.

### Setup

1. In Jellyfin go to **Dashboard → API Keys → +** and create a key (name it `dam`).
2. Add the key to `tokens.json`: `{"name": "jellyfintoken", "value": "<key>"}`
3. In `config.json`:

```json
{
    "media_servers": ["plex", "jellyfin"],
    "jellyfin_url": "http://127.0.0.1:8096",
    "jellyfin_user": "dave",
    "jellyfin_movie_library": "Movies",
    "jellyfin_favorite_threshold": 4.5,
    "jellyfin_sync_tags": true,
    "jellyfin_sync_watchlist": true
}
```

- `media_servers` sets which servers `process_letterboxd_export.py` syncs to. Use `["plex", "jellyfin"]` while you run both and `["jellyfin"]` once Plex is retired.
- `jellyfin_user` is the Jellyfin account that gets the ratings, watched status, favorites and playlists. API keys aren't tied to a user, so it has to be named here.

### Scripts

```
# Ratings, watched (with the Letterboxd watch date), favorites, plus optional tags and watchlist playlist
.venv/bin/python3 sync_lb_to_jellyfin.py --dry-run --tags --watchlist

# Jellyfin collections from plex_collections/*.txt (same lists as the Plex script)
.venv/bin/python3 add_movies_to_jellyfin_collection.py --dry-run
```

### How Letterboxd maps to Jellyfin

| Letterboxd | Jellyfin | Notes |
|---|---|---|
| Star rating | Per-user rating, 0–10 (stars × 2) | Saved and returned by the API, but the stock web UI doesn't display it |
| Rating ≥ threshold | Favorite (heart) | Shown in the UI and filterable |
| Review / diary entry | Played, dated to the watched date | |
| Tags | `lb:<tag>` item tags | Filterable in the UI. Tags are server-wide, not per-user |
| Watchlist | "Letterboxd Watchlist" playlist | Only includes movies you have |
| List files | Collections | Server-wide |

Jellyfin has nowhere to store review text. To see star ratings (and notes) in the UI, look at a ratings plugin such as [Jellyfin.Plugin.UserRating](https://github.com/aG00Dtime/Jellyfin.Plugin.UserRating) or [jellyfin-plugin-ratings](https://github.com/K3ntas/jellyfin-plugin-ratings). Those plugins keep their own storage, so the sync would have to call their APIs as well.

Tests: `python3 test/jellyfin_utils_test.py` runs against a fake server, so no Jellyfin instance is needed.
