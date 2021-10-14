import asyncio
import os
#import nacl
from config import GUILD_NAME
from test_helper import TestHelperClient
from performance_test import run_test_clients
from tournament_client import TournamentClient


if __name__ == "__main__":

  tasks = []
  tasks = run_test_clients(GUILD_NAME, os.environ['DISCORD_TEST_TOKENS'].split())

  test_helper_client = TestHelperClient(guild_name=GUILD_NAME)
  tasks.append(test_helper_client.start(os.environ['DISCORD_TEST_HELPER_TOKEN']))

  main_client = TournamentClient(guild_name=GUILD_NAME)
  tasks.append(main_client.start(os.environ['DISCORD_TOKEN']))
  #tasks.append(main_client.start(os.environ['DISCORD_TEST_HELPER_TOKEN']))

  asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))


'''
TODO BACKLOG:
- get rid of all get_* methods, instead set in the on_ready event method ?
- parallel async: await entire for loop instead of single iterations
- test giving both participant and manager roles to someone
- Exception
- GuildClient

TODO IN PROGRESS:
- traduzioni
- waiting room solo a Utenti
- summon -> send private message to who is not summoned

DONE:
- mute unmute anche in lobby
- summon all | waiting anche mobile
- mobile/offline/dnd for summon in waiting-room
- summon -> don't summon if in codenames or amongus rooms
- mobile/offline/dnd for "summon" in lobby
'''