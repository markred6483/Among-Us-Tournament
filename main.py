import os
import asyncio
#import nacl
from tournament_client import TournamentClient
from testhelper_client import TestHelperClient
from performance_test import run_test_clients
from config import GUILD_NAME


if __name__ == "__main__":

  tasks = []
  tasks = run_test_clients(GUILD_NAME, os.environ['DISCORD_TEST_TOKENS'].split())

  test_helper_client = TestHelperClient(guild_name=GUILD_NAME)
  tasks.append(test_helper_client.start(os.environ['DISCORD_TEST_HELPER_TOKEN']))

  main_client = TournamentClient(guild_name=GUILD_NAME)
  tasks.append(main_client.start(os.environ['DISCORD_TOKEN']))

  asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))


'''
TODO BACKLOG:
- get rid of all get_* methods, instead set in the on_ready event method ?
- parallel async: await entire for loop instead of single iterations
- test giving both participant and manager roles to someone
- test Direct Message from non-member (get_member)
- implement role color
- traduzioni

TODO SOON:
- waiting room solo a Utenti
- summon -> send private message to who is not summoned
- relunch: stop fetching all members at lunch, instead, save participants into DB and fetch those only

DONE:
- mute unmute anche in lobby
- mobile/offline/dnd for summon in waiting-room
- mobile/offline/dnd for "summon" in lobby
- summon -> don't summon if in codenames or amongus rooms
- summon all
- solve IndexError
- lock
'''