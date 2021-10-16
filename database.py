from replit import db
import asyncio

lock = asyncio.Lock()

async def put_participant_id(id):
  async with lock:
    try:
      db["participants"][str(id)] = True
    except KeyError:
      db["participants"] = { str(id): True }

async def del_participant_id(id):
  async with lock:
    try:
      del db["participants"][str(id)]
    except KeyError:
      return

async def get_participants_ids():
  async with lock:
    try:
      return db["participants"].keys()
    except KeyError:
      return []