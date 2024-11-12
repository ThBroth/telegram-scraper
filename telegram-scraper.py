import os
import sqlite3
import json
import csv
import asyncio
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, User, PeerChannel
from telethon.errors import FloodWaitError, RPCError
import aiohttp
import sys

import export

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

STATE_FILE = 'state.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'api_id': None,
        'api_hash': None,
        'phone': None,
        'channels': {},
        'scrape_media': True,
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

state = load_state()

if not state['api_id'] or not state['api_hash'] or not state['phone']:
    state['api_id'] = int(input("Enter your API ID: "))
    state['api_hash'] = input("Enter your API Hash: ")
    state['phone'] = input("Enter your phone number: ")
    save_state(state)

client = TelegramClient('session', state['api_id'], state['api_hash'])

def save_message_to_db(channel, message, sender):
    channel_dir = os.path.join(os.getcwd(), 'data/' + channel)
    os.makedirs(channel_dir, exist_ok=True)

    db_file = os.path.join(channel_dir, f'{channel}.db')
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute(f'''CREATE TABLE IF NOT EXISTS messages
                  (id INTEGER PRIMARY KEY, message_id INTEGER, date TEXT, sender_id INTEGER, first_name TEXT, last_name TEXT, username TEXT, message TEXT, media_type TEXT, media_path TEXT, reply_to INTEGER)''')
    c.execute('''INSERT OR IGNORE INTO messages (message_id, date, sender_id, first_name, last_name, username, message, media_type, media_path, reply_to)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (message.id, 
               message.date.strftime('%Y-%m-%d %H:%M:%S'), 
               message.sender_id,
               getattr(sender, 'first_name', None) if isinstance(sender, User) else None, 
               getattr(sender, 'last_name', None) if isinstance(sender, User) else None,
               getattr(sender, 'username', None) if isinstance(sender, User) else None,
               message.message, 
               message.media.__class__.__name__ if message.media else None, 
               None,
               message.reply_to_msg_id if message.reply_to else None))
    conn.commit()
    conn.close()

MAX_RETRIES = 5

async def download_media(channel, message):
    if not message.media or not state['scrape_media']:
        return None

    channel_dir = os.path.join(os.getcwd(), 'data/' + channel)
    media_folder = os.path.join(channel_dir, 'media')
    os.makedirs(media_folder, exist_ok=True)    
    media_file_name = None
    if isinstance(message.media, MessageMediaPhoto):
        media_file_name = message.file.name or f"{message.id}.jpg"
    elif isinstance(message.media, MessageMediaDocument):
        media_file_name = message.file.name or f"{message.id}.{message.file.ext if message.file.ext else 'bin'}"
    
    if not media_file_name:
        print(f"Unable to determine file name for message {message.id}. Skipping download.")
        return None
    
    media_path = os.path.join(media_folder, media_file_name)
    
    if os.path.exists(media_path):
        print(f"Media file already exists: {media_path}")
        return media_path

    retries = 0
    while retries < MAX_RETRIES:
        try:
            if isinstance(message.media, MessageMediaPhoto):
                media_path = await message.download_media(file=media_folder)
            elif isinstance(message.media, MessageMediaDocument):
                media_path = await message.download_media(file=media_folder)
            if media_path:
                print(f"Successfully downloaded media to: {media_path}")
            break
        except (TimeoutError, aiohttp.ClientError, RPCError) as e:
            retries += 1
            print(f"Retrying download for message {message.id}. Attempt {retries}...")
            await asyncio.sleep(2 ** retries)
    return media_path



async def scrape_channel(channel, offset_id):
    try:
        if channel.startswith('-'):
            entity = await client.get_entity(PeerChannel(int(channel)))
        else:
            entity = await client.get_entity(channel)

        total_messages = 0
        processed_messages = 0

        async for message in client.iter_messages(entity, offset_id=offset_id, reverse=True):
            total_messages += 1

        if total_messages == 0:
            print(f"No messages found in channel {channel}.")
            return

        last_message_id = None
        processed_messages = 0

        async for message in client.iter_messages(entity, offset_id=offset_id, reverse=True):
            try:
                sender = await message.get_sender()
                save_message_to_db(channel, message, sender)

                if state['scrape_media'] and message.media:
                    media_path = await download_media(channel, message)
                    if media_path:
                        conn = sqlite3.connect(os.path.join('data/' + channel, f'{channel}.db'))
                        c = conn.cursor()
                        c.execute('''UPDATE messages SET media_path = ? WHERE message_id = ?''', (media_path, message.id))
                        conn.commit()
                        conn.close()
                
                last_message_id = message.id
                processed_messages += 1

                progress = (processed_messages / total_messages) * 100
                sys.stdout.write(f"\rScraping channel: {channel} - Progress: {progress:.2f}% ")
                sys.stdout.flush()

                state['channels'][channel] = last_message_id
                save_state(state)
            except Exception as e:
                print(f"Error processing message {message.id}: {e}")
        print()
    except ValueError as e:
        print(f"Error with channel {channel}: {e}")

async def continuous_scraping():
    global continuous_scraping_active
    continuous_scraping_active = True

    try:
        while continuous_scraping_active:
            for channel in state['channels']:
                print(f"\nChecking for new messages in channel: {channel}")
                await scrape_channel(channel, state['channels'][channel])
                print(f"New messages or media scraped from channel: {channel}")
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        print("Continuous scraping stopped.")
        continuous_scraping_active = False

async def view_channels():
    if not state['channels']:
        print("No channels to view.")
        return
    
    print("\nCurrent channels:")
    # print(json.dumps(state['channels'], indent=4))
    for channel, last_id in state['channels'].items():
        print(f"Channel ID: {channel}, Last Message ID: {last_id}")

async def list_Channels():
    try:
        print("\nList of channels joined by account: ")
        async for dialog in client.iter_dialogs():
            if (dialog.id != 777000):
                print(f"* {dialog.title} (id: {dialog.id})")
    except Exception as e:
        print(f"Error processing: {e}")

async def manage_channels():
    while True:
        print("\nMenu:")
        print("[A] Add new channel")
        print("[R] Remove channel")
        print("[S] Scrape all channels")
        print("[M] Toggle media scraping (currently {})".format(
            "enabled" if state['scrape_media'] else "disabled"))
        print("[C] Continuous scraping")
        print("[E] Export data")
        print("[V] View saved channels")
        print("[L] List account channels")
        print("[Q] Quit")

        choice = input("Enter your choice: ").lower()
        match (choice):
            case 'a':
                channel = input("Enter channel ID: ")
                state['channels'][channel] = 0
                save_state(state)
                print(f"Added channel {channel}.")
            case 'r':
                channel = input("Enter channel ID to remove: ")
                if channel in state['channels']:
                    del state['channels'][channel]
                    save_state(state)
                    print(f"Removed channel {channel}.")
                else:
                    print(f"Channel {channel} not found.")
            case 's':
                for channel in state['channels']:
                    await scrape_channel(channel, state['channels'][channel])
            case 'm':
                state['scrape_media'] = not state['scrape_media']
                save_state(state)
                print(
                    f"Media scraping {'enabled' if state['scrape_media'] else 'disabled'}.")
            case 'c':
                global continuous_scraping_active
                continuous_scraping_active = True
                task = asyncio.create_task(continuous_scraping())
                print("Continuous scraping started. Press Ctrl+C to stop.")
                try:
                    await asyncio.sleep(float('inf'))
                except KeyboardInterrupt:
                    continuous_scraping_active = False
                    task.cancel()
                    print("\nStopping continuous scraping...")
                    await task
            case 'e':
                await export.export_data(state)
            case 'v':
                await view_channels()
            case 'q':
                print("Quitting...")
                sys.exit()
            case 'l':
                await list_Channels()

            case _:
                print("Invalid option.")

async def main():
    await client.start()
    while True:
        await manage_channels()

if __name__ == '__main__':
    display_ascii_art()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting...")
        sys.exit()
