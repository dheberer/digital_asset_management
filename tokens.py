import json

def get_token(name:str) -> str:
    with open('tokens.json') as f:
        # Load the JSON data as a dictionary
        data = json.load(f)
        tok_list = [x.get('value') for x in data.get('tokens', []) if x.get('name') == name]
        if tok_list:
            return tok_list[0]

