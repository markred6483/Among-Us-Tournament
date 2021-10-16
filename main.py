import os
import asyncio
#import nacl
from tournament_client import TournamentClient
from testhelper_client import TestHelperClient
from performance_test import run_test_clients
from constants import GUILD_NAME



if __name__ == "__main__":

  tasks = []
  #tasks = run_test_clients(GUILD_NAME, os.environ['DISCORD_TEST_TOKENS'].split())

  test_helper_client = TestHelperClient(guild_name=GUILD_NAME)
  tasks.append(test_helper_client.start(os.environ['DISCORD_TEST_HELPER_TOKEN']))
  
  main_client = TournamentClient(guild_name=GUILD_NAME)
  tasks.append(main_client.start(os.environ['DISCORD_TOKEN']))

  asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))


'''
TODO:
- lobbies access/visibility to prevent stream meta-gaming
- test Direct Message from non-member (get_member)
- public commands only for verified members
- "summon" -> send private message to who is not summoned
- better summon response message
- reduce intents
- traduzioni


- split start command in 2: lobbies creation + moving players
- renaming
- implement role color
- test giving both participant and manager roles to someone
- get rid of all get_* methods, instead set in the on_ready event method ?
- parallel async: await entire for loop instead of single iterations
- better summon-error-buffer management

DONE:
- mute unmute anche in lobby
- mobile/offline/dnd for summon in waiting-room
- mobile/offline/dnd for "summon" in lobby
- summon -> don't summon if in codenames or amongus rooms
- "summon" all
- solve IndexError
- commands lock
- waiting room just for verified members
- relunch: stop fetching all members at lunch, instead, save participants into DB and fetch those only
'''