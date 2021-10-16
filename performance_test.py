import discord
from base_client import BaseClient
from constants import WAITING_ROOM_NAME, WAITING_CHAT_NAME

class TestClient(BaseClient):
  
  def __init__(self, guild_name, intents=None):
    super().__init__(guild_name=guild_name, intents=intents)
    self.is_moving = False
    self.waiting_room = None
    self.waiting_chat = None

  async def on_ready(self):
    await super().on_ready()
    self.waiting_room = discord.utils.get(self.guild.channels, name=WAITING_ROOM_NAME)
    self.waiting_chat = discord.utils.get(self.guild.channels, name=WAITING_CHAT_NAME)
    await self.connect_to_waiting_room()
    #await self.join_tournament()
  
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


def run_test_clients(guild_name, tokens):
  print(f'Running {len(tokens)} test clients')
  clients = []
  tasks = []
  for t in tokens:
    c = TestClient(guild_name=guild_name)
    clients.append(c)
    tasks.append(c.start(t))
  return tasks