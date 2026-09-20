#!/usr/bin/env python3
"""
Remap moved movies in Radarr.

Finds movies where Radarr's stored path doesn't match where the file
actually lives on disk. Updates Radarr's database to point to the
correct location.

Usage:
    python3 radarr_remap.py                        # dry-run, show what would change
    python3 radarr_remap.py --apply                # actually update Radarr

Requirements:
    pip install requests
"""

import argparse
import requests
import sys
import os
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────
RADARR_URL = "http://localhost:7878"
RADARR_API_KEY = ""  # Set here or pass via --api-key or RADARR_API_KEY env var

# All root folders where movies might live
SEARCH_DIRS = [
    "/media/nas/Movies",
    "/media/nas2/Movies",
]
# ───────────────────────────────────────────────────────────────


def get_api_key(args):
    """Get Radarr API key from args, env, or config."""
    if args.api_key:
        return args.api_key
    if RADARR_API_KEY:
        return RADARR_API_KEY
    env_key = os.environ.get("RADARR_API_KEY")
    if env_key:
        return env_key
    print("ERROR: No Radarr API key provided.")
    print("  Pass it with --api-key YOUR_KEY")
    print("  Or set RADARR_API_KEY environment variable")
    print("  Or edit RADARR_API_KEY in this script")
    print()
    print("  Find your API key in Radarr: Settings → General → API Key")
    sys.exit(1)


def radarr_get(base_url, api_key, endpoint):
    """GET request to Radarr API."""
    headers = {"X-Api-Key": api_key}
    resp = requests.get(f"{base_url}/api/v3/{endpoint}", headers=headers)
    resp.raise_for_status()
    return resp.json()


def radarr_put(base_url, api_key, endpoint, data):
    """PUT request to Radarr API."""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    resp = requests.put(f"{base_url}/api/v3/{endpoint}", headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()


def radarr_post(base_url, api_key, endpoint, data):
    """POST request to Radarr API."""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    resp = requests.post(f"{base_url}/api/v3/{endpoint}", headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()


def build_disk_index(search_dirs):
    """Build an index of movie folder names to their full paths on disk.
    
    Returns dict: normalized_folder_name -> [full_path, ...]
    """
    index = {}
    for search_dir in search_dirs:
        search_path = Path(search_dir)
        if not search_path.is_dir():
            print(f"  WARNING: Search directory not found: {search_dir}")
            continue
        for entry in search_path.iterdir():
            if entry.is_dir() and not entry.name.startswith('.'):
                name = entry.name.lower().strip()
                if name not in index:
                    index[name] = []
                index[name].append(str(entry))
    return index


def has_video_files(folder_path):
    """Check if a folder contains any video files."""
    video_extensions = {'.mkv', '.mp4', '.avi', '.m4v', '.ts', '.wmv', '.flv', '.mov'}
    folder = Path(folder_path)
    if not folder.is_dir():
        return False
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in video_extensions:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Remap moved movies in Radarr to their correct paths."
    )
    parser.add_argument(
        '--api-key', type=str, default=None,
        help='Radarr API key.'
    )
    parser.add_argument(
        '--url', type=str, default=RADARR_URL,
        help=f'Radarr URL (default: {RADARR_URL}).'
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='Actually update paths in Radarr. Without this, just shows what would change.'
    )
    parser.add_argument(
        '--rescan', action='store_true',
        help='Trigger a rescan of remapped movies after updating (use with --apply).'
    )
    args = parser.parse_args()

    api_key = get_api_key(args)
    base_url = args.url.rstrip('/')

    mode = "APPLY MODE" if args.apply else "DRY RUN"
    print(f"{'='*70}")
    print(f"  Radarr Movie Remapper — {mode}")
    print(f"{'='*70}")
    print()

    # Test connection
    try:
        status = radarr_get(base_url, api_key, "system/status")
        print(f"  Connected to Radarr v{status.get('version', 'unknown')}")
    except Exception as e:
        print(f"ERROR: Cannot connect to Radarr at {base_url}: {e}")
        sys.exit(1)

    # Build disk index
    print()
    print(f"  Building disk index from:")
    for d in SEARCH_DIRS:
        print(f"    - {d}")
    disk_index = build_disk_index(SEARCH_DIRS)
    print(f"  Found {len(disk_index)} unique movie folders on disk")
    print()

    # Get all movies from Radarr
    movies = radarr_get(base_url, api_key, "movie")
    print(f"  Radarr has {len(movies)} movies in database")
    print()

    # Categorize movies
    ok_count = 0
    missing_count = 0
    remap_count = 0
    not_found_count = 0
    errors = []

    remaps = []
    missing = []
    not_found = []

    for movie in movies:
        title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        display = f"{title} ({year})" if year else title
        radarr_path = movie.get("path", "")
        movie_id = movie.get("id")

        # Check if Radarr's path exists and has video files
        if os.path.isdir(radarr_path) and has_video_files(radarr_path):
            ok_count += 1
            continue

        # Path is wrong — try to find the movie on disk
        folder_name = os.path.basename(radarr_path.rstrip('/'))
        normalized = folder_name.lower().strip()

        candidates = disk_index.get(normalized, [])

        # Filter to candidates that actually have video files
        valid_candidates = [c for c in candidates if has_video_files(c)]

        if len(valid_candidates) == 1:
            new_path = valid_candidates[0]
            if new_path != radarr_path:
                remaps.append({
                    "movie": movie,
                    "display": display,
                    "old_path": radarr_path,
                    "new_path": new_path,
                })
                remap_count += 1
            else:
                # Same path but no video files? Weird.
                missing.append((display, radarr_path))
                missing_count += 1

        elif len(valid_candidates) > 1:
            # Multiple matches — pick the one that's different from current path
            others = [c for c in valid_candidates if c != radarr_path]
            if len(others) == 1:
                remaps.append({
                    "movie": movie,
                    "display": display,
                    "old_path": radarr_path,
                    "new_path": others[0],
                })
                remap_count += 1
            else:
                # Ambiguous — report but don't auto-remap
                print(f"  AMBIGUOUS: {display}")
                print(f"    Radarr path: {radarr_path}")
                for c in valid_candidates:
                    print(f"    Found at:    {c}")
                print()
                not_found.append((display, radarr_path))
                not_found_count += 1
        else:
            # Not found anywhere on disk
            not_found.append((display, radarr_path))
            not_found_count += 1

    # Report remaps
    if remaps:
        print(f"  {'─'*66}")
        print(f"  REMAPS ({len(remaps)} movies can be fixed)")
        print(f"  {'─'*66}")
        print()

        for r in remaps:
            print(f"  {r['display']}")
            print(f"    OLD: {r['old_path']}")
            print(f"    NEW: {r['new_path']}")

            if args.apply:
                try:
                    movie_data = r["movie"]
                    movie_data["path"] = r["new_path"]
                    radarr_put(base_url, api_key, f"movie/{movie_data['id']}", movie_data)
                    print(f"    ✓ Updated in Radarr")

                    if args.rescan:
                        radarr_post(base_url, api_key, "command", {
                            "name": "RescanMovie",
                            "movieId": movie_data["id"],
                        })
                        print(f"    ✓ Rescan triggered")

                except Exception as e:
                    errors.append((r["display"], str(e)))
                    print(f"    ✗ Error: {e}")
            else:
                print(f"    → Would remap")

            print()

    # Report not found
    if not_found:
        print(f"  {'─'*66}")
        print(f"  NOT FOUND ON DISK ({len(not_found)} movies)")
        print(f"  {'─'*66}")
        print()
        for display, path in not_found:
            print(f"  {display}")
            print(f"    Expected: {path}")
        print()

    # Summary
    print(f"{'='*70}")
    print(f"  Summary:")
    print(f"    OK (path correct):      {ok_count}")
    print(f"    Remapped:               {remap_count}")
    print(f"    Not found on disk:      {not_found_count}")
    if errors:
        print(f"    Errors:                 {len(errors)}")
        for display, err in errors:
            print(f"      - {display}: {err}")
    print()
    if not args.apply and remap_count > 0:
        print(f"  Run with --apply to update Radarr.")
        print(f"  Run with --apply --rescan to also trigger file rescans.")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
