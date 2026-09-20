import json
from pathlib import Path

def get_token(name:str) -> str:
    fq_filename = Path(__file__).parent / "tokens.json"

    with open(fq_filename) as f:
        # Load the JSON data as a dictionary
        data = json.load(f)
        tok_list = [x.get('value') for x in data.get('tokens', []) if x.get('name') == name]
        if tok_list:
            return tok_list[0]

