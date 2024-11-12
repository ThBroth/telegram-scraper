import os
import json

STATE_FILE = 'state.json'

def display_ascii_art():
    WHITE = "\033[97m"
    RESET = "\033[0m"

    art = r"""
___________________  _________
\__    ___/  _____/ /   _____/
  |    | /   \  ___ \_____  \ 
  |    | \    \_\  \/        \
  |____|  \______  /_______  /
                 \/        \/
    """

    print(WHITE + art + RESET)

def load_state(STATE_FILE):
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    else:
        apiID = int(input("Enter your API ID: "))
        apiHash = input("Enter your API Hash: ")
        phone = input("Enter your phone number: ")

    return {
        'api_id': apiID,
        'api_hash': apiHash,
        'phone': phone,
        'channels': {},
        'scrape_media': True,
    }

def save_state(state, STATE_FILE):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
