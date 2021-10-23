from replit import db
import asyncio

lock = asyncio.Lock()

async def put_participant_id(guild_name, id):
  async with lock:
    try:
      db[guild_name]["participants"][str(id)] = True
    except:
      db[guild_name] = {"participants": { str(id): True } }

async def del_participant_id(guild_name, id):
  async with lock:
    try:
      del db[guild_name]["participants"][str(id)]
    except:
      return

async def get_participants_ids(guild_name):
  async with lock:
    try:
      return db[guild_name]["participants"].keys()
    except:
      return []

def reset_db(guild_name):
  try:
    del db[guild_name]
  except:
    pass