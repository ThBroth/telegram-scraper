from config import save_state
from config import STATE_FILE
from telethon.tl.types import Channel

async def add_channel(state, channel):
    state['channels'][channel] = 0
    save_state(state, STATE_FILE)
    return(f"Added channel {channel}.")


async def remove_channel(state, channel):
    if channel in state['channels']:
        del state['channels'][channel]
        save_state(state, STATE_FILE)
        return(f"Removed channel {channel}.")
    else:
        return(f"Channel {channel} not found.")

async def view_channels(state):
    if not state['channels']:
        print("No channels to view.")
        return

    print("\nCurrent channels:")
    for channel, last_id in state['channels'].items():
        print(f"Channel ID: {channel}, Last Message ID: {last_id}")

async def list_Channels(clientInput):
    try:
        print("\nList of channels joined by account: ")
        async for dialog in clientInput.iter_dialogs():
            if isinstance(dialog.entity, Channel):
                print(f"* {dialog.title} (id: {dialog.id})")
    except Exception as e:
        print(f"Error processing: {e}")
