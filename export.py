import os
import sqlite3
import json
import csv

async def export_data(input):
    print('\nExporting data')
    for channel in input['channels']:
        print(channel)
        export_to_csv(channel)
        export_to_json(channel)

def export_to_csv(channel):
    db_file = os.path.join('data/' + channel, f'{channel}.db')
    csv_file = os.path.join('data/' + channel, f'{channel}.csv')
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('SELECT * FROM messages')
    rows = c.fetchall()
    conn.close()

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([description[0] for description in c.description])
        writer.writerows(rows)

def export_to_json(channel):
    db_file = os.path.join('data/' + channel, f'{channel}.db')
    json_file = os.path.join('data/' + channel, f'{channel}.json')
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('SELECT * FROM messages')
    rows = c.fetchall()
    conn.close()

    data = [dict(zip([description[0] for description in c.description], row))
            for row in rows]
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


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
               getattr(sender, 'first_name', None),
               getattr(sender, 'last_name', None),
               getattr(sender, 'username', None),
               message.message,
               message.media.__class__.__name__ if message.media else None,
               None,
               message.reply_to_msg_id if message.reply_to else None))
    conn.commit()
    conn.close()
