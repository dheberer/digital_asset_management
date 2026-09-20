import json
from pathlib import Path


def get_config(name: str, default=None):
    fq_filename = Path(__file__).parent / "config.json"

    with open(fq_filename) as f:
        data = json.load(f)
        return data.get(name, default)
