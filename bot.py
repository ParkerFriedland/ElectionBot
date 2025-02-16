import discord
import csv
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.message_content = True
intents.members = True

bot = discord.Bot(intents=intents)
CSV_FILE = 'votes.csv'
CANDIDATE_CHANNEL_ID = int(os.getenv('CANDIDATE_CHANNEL_ID'))

def read_csv():
    try:
        with open(CSV_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except FileNotFoundError:
        return []

def write_csv(data):
    if not data:
        return
    headers = ['User ID', 'Last Modified'] + [
        col for col in data[0].keys() 
        if col not in ('User ID', 'Last Modified')
    ]
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

async def sync_columns():
    channel = bot.get_channel(CANDIDATE_CHANNEL_ID)
    if not channel:
        return
        
    try:
        messages = await channel.history(limit=None).flatten()
    except discord.errors.Forbidden:
        return

    current_message_ids = {str(msg.id) for msg in messages}
    data = read_csv()
    
    if not data:
        return

    existing_headers = set(data[0].keys())
    new_headers = {'User ID', 'Last Modified'}.union(current_message_ids)
    
    # Add missing columns
    for header in new_headers - existing_headers:
        for row in data:
            row[header] = row.get(header, '')
    
    # Remove deleted columns
    for header in existing_headers - new_headers:
        for row in data:
            if header in row:
                del row[header]
    
    write_csv(data)

@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user}')
    await sync_columns()

@bot.event
async def on_message(message):
    if message.channel.id != CANDIDATE_CHANNEL_ID or message.author.bot:
        return

    data = read_csv()
    message_id = str(message.id)
    
    if data and message_id not in data[0]:
        for row in data:
            row[message_id] = ''
        write_csv(data)

@bot.event
async def on_raw_message_delete(payload):
    if payload.channel_id != CANDIDATE_CHANNEL_ID:
        return

    message_id = str(payload.message_id)
    data = read_csv()
    
    if data and message_id in data[0]:
        for row in data:
            if message_id in row:
                del row[message_id]
        write_csv(data)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or reaction.message.channel.id != CANDIDATE_CHANNEL_ID:
        return

    data = read_csv()
    message_id = str(reaction.message.id)
    user_id = str(user.id)
    now = datetime.now().isoformat()

    # Find or create user row
    user_row = next((r for r in data if r['User ID'] == user_id), None)
    if not user_row:
        user_row = {'User ID': user_id, 'Last Modified': now}
        for col in data[0].keys() if data else []:
            if col not in user_row:
                user_row[col] = ''
        data.append(user_row)

    # Update vote and timestamp
    user_row[message_id] = 'X'
    user_row['Last Modified'] = now
    write_csv(data)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot or reaction.message.channel.id != CANDIDATE_CHANNEL_ID:
        return

    try:
        message = await reaction.message.channel.fetch_message(reaction.message.id)
    except discord.NotFound:
        return

    # Check if user has any remaining reactions
    has_reactions = any(
        user.id in await r.users().flatten()
        for r in message.reactions
    )

    if not has_reactions:
        data = read_csv()
        user_id = str(user.id)
        message_id = str(message.id)
        now = datetime.now().isoformat()

        user_row = next((r for r in data if r['User ID'] == user_id), None)
        if user_row and message_id in user_row:
            user_row[message_id] = ''
            user_row['Last Modified'] = now
            write_csv(data)

bot.run(os.getenv('BOT_TOKEN'))
