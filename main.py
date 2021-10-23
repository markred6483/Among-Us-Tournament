import os
import asyncio
#import nacl
from tournament_client import TournamentClient
from performance_test import run_test_clients
#from replit import db
from constants import GUILD_NAME, TESTING

if __name__ == "__main__":

  tasks = []
  if TESTING:
    tasks = run_test_clients()
  main_client = TournamentClient(guild_name=GUILD_NAME)
  tasks.append(main_client.start(os.environ['DISCORD_TOKEN']))
  asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks))

'''
TODO:
- test summon errors
- better summon response message + summon-error-buffer management
- better channels permissions (e.g: lobbies access/visibility to prevent stream meta-gaming)
- traduzioni
- direct message commands
    - test Direct Message from non-member (get_member)
    - public commands only for verified members
- split start command in 2: lobbies creation + moving players
- renaming
- implement role color
- test giving both participant and manager roles to someone
- get rid of all get_* methods, instead set in the on_ready event method ?
- parallel async: await entire for loop instead of single iterations
- monitor to prevent on_message firing before on_ready

'''