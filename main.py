import os
import sqlite3
import asyncio
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, User, PeerChannel
from telethon.errors import FloodWaitError, RPCError
import aiohttp
import sys
import argparse

import export
import channels
import config

MEDIA_MAX_RETRIES = 5

state = config.load_state(config.STATE_FILE)
config.save_state(state, config.STATE_FILE)
client = TelegramClient('session', state['api_id'], state['api_hash'])

parser = argparse.ArgumentParser(
    description="A powerful Python script that allows you to scrape messages and media from Telegram channels using the Telethon library. Features include real-time continuous scraping, media downloading, and data export capabilities.")
parser.add_argument("--add", "-a", metavar="id", help="Add new channel")
parser.add_argument("--remove", "-r", metavar="id", help="Remove channel")
parser.add_argument("--scrape", "-s", action="store_true", help="Scrape all channels")
parser.add_argument("--toggle", "-t", action="store_true", help="Toggle media scraping")
parser.add_argument("--continuous", "-c", action="store_true", help="Continuous scraping")
parser.add_argument("--export", "-e", action="store_true", help="Export data")
parser.add_argument("--view", "-v", action="store_true", help="View saved channels")
parser.add_argument("--list", "-l", action="store_true", help="List account channels")
args = parser.parse_args()


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
    while retries < MEDIA_MAX_RETRIES:
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
                # print("\n\nTHE SHIT\n\n", sender, "\n\nTHE SHIT OVER\n\n")
                export.save_message_to_db(channel, message, sender)

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
                config.save_state(state, config.STATE_FILE)
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
                print(await channels.add_channel(state, channel))

            case 'r':
                channel = input("Enter channel ID to remove: ")
                print(await channels.remove_channel(state, channel))

            case 's':
                for channel in state['channels']:
                     await scrape_channel(channel, state['channels'][channel])

            case 'm':
                state['scrape_media'] = not state['scrape_media']
                config.save_state(state, config.STATE_FILE)
                print(f"Media scraping {'enabled' if state['scrape_media'] else 'disabled'}.")
                
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
                await channels.view_channels(state)

            case 'l':
                await channels.list_Channels(client)

            case 'q':
                print("Quitting...")
                sys.exit()

            case _:
                print("Invalid option.")

async def main():
    await client.start()
    if not any(vars(args).values()):
            try:
                while True:
                    await manage_channels()
            except KeyboardInterrupt:
                print("\nProgram interrupted. Exiting...")
                sys.exit()
    else:
        if args.add:
            channel = args.add
            print(await channels.add_channel(state, channel))

        if args.remove:
            channel = args.remove
            print(await channels.remove_channel(state, channel))

        if args.scrape:
            for channel in state['channels']:
                await scrape_channel(channel, state['channels'][channel])

        if args.continuous:
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

        if args.toggle:
            state['scrape_media'] = not state['scrape_media']
            config.save_state(state, config.STATE_FILE)
            print(f"Media scraping {'enabled' if state['scrape_media'] else 'disabled'}.")

        if args.export:
            await export.export_data(state)

        if args.view:
            await channels.view_channels(state)

        if args.list:
            await channels.list_Channels(client)

if __name__ == '__main__':
    config.display_ascii_art()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting...")
        sys.exit()