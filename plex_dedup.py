#!/usr/bin/env python3
"""
Find duplicate movies using the Plex API.

Plex already matches movies by metadata (TMDB/IMDB), so "28 Days Later"
and "28 Days Later..." are recognized as the same movie. This script finds
movies with multiple media files, compares them, and optionally deletes
the smaller (lower quality) copy.

Usage:
    python3 plex_dedup.py                          # dry-run
    python3 plex_dedup.py --delete                 # actually delete
    python3 plex_dedup.py --prefer /media/nas2     # prefer files in nas2 when sizes are close

Requirements:
    pip install requests
"""

import argparse
import requests
import sys
import os
import shutil
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────
PLEX_URL = "http://localhost:32400"
PLEX_TOKEN = ""  # Set here or pass via --token or PLEX_TOKEN env var
# ───────────────────────────────────────────────────────────────


def get_token(args):
    """Get Plex token from args, env, or config."""
    if args.token:
        return args.token
    if PLEX_TOKEN:
        return PLEX_TOKEN
    env_token = os.environ.get("PLEX_TOKEN")
    if env_token:
        return env_token
    print("ERROR: No Plex token provided.")
    print("  Pass it with --token YOUR_TOKEN")
    print("  Or set PLEX_TOKEN environment variable")
    print("  Or edit PLEX_TOKEN in this script")
    sys.exit(1)


def plex_get(url, token, params=None):
    """Make a GET request to the Plex API."""
    headers = {
        "X-Plex-Token": token,
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def human_size(num_bytes):
    """Format bytes as human-readable string."""
    if num_bytes is None or num_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def human_bitrate(kbps):
    """Format kbps as human-readable string."""
    if kbps is None:
        return "unknown"
    if kbps >= 1000:
        return f"{kbps/1000:.1f} Mbps"
    return f"{kbps} kbps"


def get_movie_libraries(base_url, token):
    """Get all movie library section IDs."""
    data = plex_get(f"{base_url}/library/sections", token)
    libraries = []
    for section in data.get("MediaContainer", {}).get("Directory", []):
        if section.get("type") == "movie":
            libraries.append({
                "key": section["key"],
                "title": section["title"],
            })
    return libraries


def get_all_movies(base_url, token, section_key):
    """Get all movies in a library section."""
    data = plex_get(f"{base_url}/library/sections/{section_key}/all", token)
    return data.get("MediaContainer", {}).get("Metadata", [])


def extract_media_info(media_item):
    """Extract useful info from a Plex media item."""
    parts = media_item.get("Part", [])
    file_path = parts[0].get("file", "unknown") if parts else "unknown"
    file_size = parts[0].get("size", 0) if parts else 0

    # Sum size across all parts (for multi-file movies)
    total_size = sum(p.get("size", 0) for p in parts)

    return {
        "file": file_path,
        "folder": str(Path(file_path).parent) if file_path != "unknown" else "unknown",
        "size": total_size,
        "bitrate": media_item.get("bitrate"),
        "width": media_item.get("width"),
        "height": media_item.get("height"),
        "video_codec": media_item.get("videoCodec"),
        "audio_codec": media_item.get("audioCodec"),
        "container": media_item.get("container"),
        "video_resolution": media_item.get("videoResolution"),
        "id": media_item.get("id"),
    }


def score_media(info, prefer_path=None):
    """Score a media item for quality comparison.
    
    Higher score = better quality = keep this one.
    Primary: file size (bigger = better quality)
    Tiebreaker: prefer_path if specified
    """
    score = info["size"]

    # Small bonus for preferred path
    if prefer_path and prefer_path in info["file"]:
        score += 1  # tiny tiebreaker, won't override size difference

    return score


def find_duplicates(base_url, token):
    """Find all movies with multiple media versions."""
    libraries = get_movie_libraries(base_url, token)
    if not libraries:
        print("ERROR: No movie libraries found in Plex.")
        sys.exit(1)

    print(f"  Found {len(libraries)} movie library(ies):")
    for lib in libraries:
        print(f"    - {lib['title']} (section {lib['key']})")
    print()

    duplicates = []

    for lib in libraries:
        movies = get_all_movies(base_url, token, lib["key"])
        print(f"  Scanning '{lib['title']}': {len(movies)} movies")

        for movie in movies:
            media_list = movie.get("Media", [])
            if len(media_list) < 2:
                continue

            media_infos = [extract_media_info(m) for m in media_list]

            # Only consider it a duplicate if files are in different directories
            unique_folders = set(m["folder"] for m in media_infos)
            if len(unique_folders) < 2:
                # Same folder, might be different editions — skip
                # (or user has two copies in the same dir, which is unusual)
                continue

            duplicates.append({
                "title": movie.get("title", "Unknown"),
                "year": movie.get("year", ""),
                "rating_key": movie.get("ratingKey"),
                "media": media_infos,
            })

    return duplicates


def delete_via_plex(base_url, token, rating_key, media_id):
    """Delete a specific media item via the Plex API.
    
    Note: Plex API can delete an entire movie entry but not individual
    media items easily. We'll delete the file directly instead.
    """
    # Plex doesn't expose per-media deletion via API cleanly,
    # so we delete the file from disk and let the user rescan.
    pass


def main():
    parser = argparse.ArgumentParser(
        description="Find duplicate movies in Plex and keep the best quality copy."
    )
    parser.add_argument(
        '--token', type=str, default=None,
        help='Plex authentication token.'
    )
    parser.add_argument(
        '--url', type=str, default=PLEX_URL,
        help=f'Plex server URL (default: {PLEX_URL}).'
    )
    parser.add_argument(
        '--delete', action='store_true',
        help='Actually delete the lower-quality duplicates.'
    )
    parser.add_argument(
        '--prefer', type=str, default=None,
        help='Path fragment to prefer when sizes are equal (e.g., /media/nas2).'
    )
    parser.add_argument(
        '--min-size-diff', type=float, default=0,
        help='Minimum size difference in MB to consider one copy better. '
             'Below this threshold, --prefer decides. (default: 0)'
    )
    args = parser.parse_args()

    token = get_token(args)
    base_url = args.url.rstrip('/')

    mode = "DELETE MODE" if args.delete else "DRY RUN"
    print(f"{'='*70}")
    print(f"  Plex Duplicate Movie Finder — {mode}")
    print(f"{'='*70}")
    print()

    # Test connection
    try:
        identity = plex_get(f"{base_url}/identity", token)
        server_name = identity.get("MediaContainer", {}).get("machineIdentifier", "unknown")
        print(f"  Connected to Plex server")
    except Exception as e:
        print(f"ERROR: Cannot connect to Plex at {base_url}: {e}")
        sys.exit(1)

    print()

    # Find duplicates
    duplicates = find_duplicates(base_url, token)

    if not duplicates:
        print()
        print("  No duplicates found!")
        return

    print()
    print(f"  Found {len(duplicates)} movies with multiple copies")
    print(f"{'='*70}")
    print()

    total_freed = 0
    delete_count = 0
    errors = []

    for dup in duplicates:
        title = f"{dup['title']} ({dup['year']})" if dup['year'] else dup['title']

        # Score each media item
        scored = []
        for m in dup["media"]:
            s = score_media(m, prefer_path=args.prefer)
            scored.append((s, m))

        # Sort by score, highest first
        scored.sort(key=lambda x: x[0], reverse=True)

        keep_score, keep = scored[0]
        removes = scored[1:]

        # If min-size-diff is set, check if the difference is meaningful
        if args.min_size_diff > 0 and len(scored) == 2:
            size_diff_mb = abs(scored[0][1]["size"] - scored[1][1]["size"]) / (1024 * 1024)
            if size_diff_mb < args.min_size_diff:
                # Difference too small — use prefer path or skip
                if args.prefer:
                    for s, m in scored:
                        if args.prefer in m["file"]:
                            keep = m
                            removes = [(s2, m2) for s2, m2 in scored if m2 is not m]
                            break
                else:
                    print(f"  {title}")
                    print(f"    SKIPPED — size difference ({size_diff_mb:.1f} MB) below threshold")
                    print()
                    continue

        # Display
        print(f"  {title}")

        for s, m in scored:
            marker = "KEEP  " if m is keep else "DELETE"
            res = m['video_resolution'] or '?'
            codec = m['video_codec'] or '?'
            bitrate = human_bitrate(m['bitrate'])
            print(f"    [{marker}] {m['file']}")
            print(f"             {human_size(m['size'])}  |  {res}p {codec}  |  {bitrate}  |  {m['container'] or '?'}")

        for _, m in removes:
            freed = m["size"]
            total_freed += freed
            folder = m["folder"]

            if args.delete:
                try:
                    # Delete the entire movie folder
                    if os.path.isdir(folder):
                        shutil.rmtree(folder)
                        delete_count += 1
                        print(f"    ✓ Deleted folder: {folder}")
                    elif os.path.isfile(m["file"]):
                        os.remove(m["file"])
                        delete_count += 1
                        print(f"    ✓ Deleted file: {m['file']}")
                    else:
                        print(f"    ✗ Not found: {folder}")
                        errors.append((folder, "Path not found"))
                except OSError as e:
                    errors.append((folder, str(e)))
                    print(f"    ✗ Error: {e}")
            else:
                delete_count += 1
                print(f"    → Would free: {human_size(freed)}")

        print()

    # Summary
    print(f"{'='*70}")
    if args.delete:
        print(f"  Deleted: {delete_count} duplicate copies")
        print(f"  Space freed: {human_size(total_freed)}")
        if errors:
            print(f"  Errors: {len(errors)}")
            for path, err in errors:
                print(f"    - {path}: {err}")
        print()
        print(f"  Next steps:")
        print(f"    1. In Plex: Settings → Libraries → Scan Library Files")
        print(f"       (to remove deleted entries)")
        print(f"    2. In Plex: Settings → Libraries → Empty Trash")
        print(f"       (to clean up metadata)")
        print(f"    3. In Radarr: check that remaining paths are correct")
    else:
        print(f"  Would delete: {delete_count} duplicate copies")
        print(f"  Would free: {human_size(total_freed)}")
        print()
        print(f"  Run with --delete to actually remove duplicates.")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
