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
