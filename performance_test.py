import os
import discord
from base_client import BaseClient
from constants import GUILD_NAME, WAITING_ROOM_NAME, WAITING_CHAT_NAME, VERIFIED_ROLE_NAME

class TestHelperClient(BaseClient):
  
  def __init__(self, guild_name):
    intents = discord.Intents.default()
    intents.members = True # to get all the members of the guild at start-up
    intents.presences = True # to know who is on mobile
    super().__init__(guild_name=guild_name, intents=intents)
    self.is_moving = False
    self.waiting_room = None

  async def on_ready(self):
    self.waiting_room = discord.utils.get(self.guild.channels, name=WAITING_ROOM_NAME)
    await self.connect_to_waiting_room()
  
  async def on_guild_channel_create(self, channel):
    if channel.name == WAITING_ROOM_NAME:
      self.waiting_room = channel
      await self.connect_to_waiting_room() 
  
  async def connect_to_waiting_room(self):
    if self.waiting_room:
      print(f'{self.user} connecting to waiting room...')
      self.is_moving = True
      await self.connect_to(self.waiting_room)
      self.is_moving = False
  
  async def on_message(self, msg):
    if msg.author.id == 705143640519082065:
      if msg.content.upper() == "TERMINATE":
        await self.close()
      elif msg.content.upper() == "VERIFY":
        print("Verifying everybody...")
        verified_role = discord.utils.get(self.guild.roles, name=VERIFIED_ROLE_NAME)
        async for member in self.guild.fetch_members(limit=50000):
          await self.give_role(member, verified_role)
      elif msg.content.upper() == "UNVERIFY":
        print("Unverifying everybody...")
        verified_role = discord.utils.get(self.guild.roles, name=VERIFIED_ROLE_NAME)
        async for member in self.guild.fetch_members(limit=50000):
          await self.revoke_role(member, verified_role)


class TestClient(BaseClient):
  
  def __init__(self, guild_name):
    intents=discord.Intents.default()
    intents.presences = False
    super().__init__(guild_name=guild_name, intents=intents)
    self.is_moving = False
    self.waiting_room = None
    self.waiting_chat = None

  async def on_ready(self):
    self.waiting_room = discord.utils.get(self.guild.channels, name=WAITING_ROOM_NAME)
    self.waiting_chat = discord.utils.get(self.guild.channels, name=WAITING_CHAT_NAME)
    await self.connect_to_waiting_room()
    await self.join_tournament()
  
  async def on_guild_channel_create(self, channel):
    if channel.name == WAITING_ROOM_NAME:
      self.waiting_room = channel
      await self.connect_to_waiting_room() 
    elif channel.name == WAITING_CHAT_NAME:
      self.waiting_chat = channel
      await self.join_tournament()
  
  async def connect_to_waiting_room(self):
    if self.waiting_room:
      print(f'{self.user} connecting to waiting room...')
      self.is_moving = True
      await self.connect_to(self.waiting_room)
      self.is_moving = False
  
  async def join_tournament(self):
    if self.waiting_chat:
      print(f'{self.user} joining tournament...')
      await self.waiting_chat.send('jOiN')
  
  async def on_message(self, msg):
    if msg.author.id == 705143640519082065 and msg.content.upper() == "TERMINATE":
      await self.close()


def run_test_clients():
  test_client_tokens = os.environ['DISCORD_TEST_TOKENS'].split()
  print(f'Running {len(test_client_tokens)} test clients')
  clients = []
  tasks = []
  for t in test_client_tokens:
    c = TestClient(guild_name=GUILD_NAME)
    clients.append(c)
    tasks.append(c.start(t))
  test_helper_client = TestHelperClient(guild_name=GUILD_NAME)
  tasks.append(test_helper_client.start(os.environ['DISCORD_TEST_HELPER_TOKEN']))
  return tasks