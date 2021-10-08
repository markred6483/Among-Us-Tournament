import discord
#import nacl
from rules import *
from baseclient import BaseClient
import os

GUILD_NAME = "markred's server"
CHILL_ROOM_NAME = "General"
CATEGORY_CHANNEL_NAME = "Among Us Tournament"
WAITING_CHAT_NAME = "chat"
WAITING_ROOM_NAME = "Waiting Room"
LOBBY_NAME_PREFIX = "Lobby Room "
LOBBY_ROLE_PREFIX = "Among Us Tournament - Lobby "
MANAGER_ROLE_NAME = "Among Us Tournament - Manager"
PARTICIPANT_ROLE_NAME = "Among Us Tournament - Participant"
BANNED_ROLE_NAME = "Among Us Tournament - Banned"

class CustomClient(BaseClient):
  
  def __init__(self, guild_name, intents):
    super().__init__(guild_name=guild_name, intents=intents)
    self.rules = [
      LogDirectMessageRule(self),
      PrepareCmdRule(self),
      CleanCmdRule(self),
      PromoteCmdRule(self),
      DemoteCmdRule(self),
      SummonCmdRule(self),
      StartCmdRule(self),
      EndCmdRule(self),
      BroadcastCmdRule(self),
      MuteCmdRule(self),
      UnmuteCmdRule(self),
      BringCmdRule(self),
      KickCmdRule(self),
      BanCmdRule(self),
      UnbanCmdRule(self),
      JoinCmdRule(self),
      QuitCmdRule(self),
    ]
    self.chill_room = None
    self.reset()
  
  def reset(self):
    self.category_channel = None
    self.waiting_chat = None
    self.waiting_room = None
    self.lobbies = None
    self.manager_role = None
    self.participant_role = None
    self.banned_role = None
  
  async def on_ready(self):
    await super().on_ready()
    # Cache members for later use
    members = await self.guild.fetch_members(limit=50000).flatten()
    print(f'{len(members)} members fetched')
    await self.prepare()
  
  async def connect_to_waiting_room(self):
    if self.get_waiting_room():
      await self.connect_to(self.waiting_room)
  
  async def on_message(self, msg):
    for processor in self.rules:
      if await processor.process(msg):
        return
  
  async def on_voice_state_update(self, member, voice_state1, voice_state2):
    if voice_state1.channel != voice_state2.channel:
      waiting_room = self.get_waiting_room()
      if waiting_room:
        if voice_state1.channel == waiting_room:
          print(f'{member} exits {voice_state1.channel.name}')
        elif voice_state2.channel == waiting_room:
          print(f'{member} enters {voice_state2.channel.name}')
    #print(f'\non_voice_state_update:\n{member}\n{voice_state1}\n{voice_state2}\n')

  async def execute_old_commands(self):
    already_done = set()
    async for msg in self.get_waiting_chat().history(limit=10000):
      if msg.author.id == client.user.id:
        break
      if discord.utils.get(msg.reactions, me=True):
        break
      if not msg.author in already_done:
        if await JoinCmdRule(self).process(msg) or await QuitCmdRule(self).process(msg):
          already_done.add(msg.author)
  
  async def prepare(self):
    if not self.get_manager_role():
      self.manager_role = await self.create_role(
        MANAGER_ROLE_NAME)
    if not self.get_participant_role():
      self.participant_role = await self.create_role(
        PARTICIPANT_ROLE_NAME)
    if not self.get_banned_role():
      self.banned_role = await self.create_role(
        BANNED_ROLE_NAME)
    if not self.get_tournament_category():
      self.category_channel = await self.create_category_channel(
        CATEGORY_CHANNEL_NAME)
    if not self.get_waiting_chat():
      self.waiting_chat = await self.create_text_channel(
        WAITING_CHAT_NAME, self.category_channel, {
          self.banned_role: discord.PermissionOverwrite(
            send_messages=False )})
    if not self.get_waiting_room():
      self.waiting_room = await self.create_voice_channel(
        WAITING_ROOM_NAME, self.category_channel, {
          self.guild.default_role: discord.PermissionOverwrite(speak=False),
          self.participant_role: discord.PermissionOverwrite(speak=True),
          self.manager_role: discord.PermissionOverwrite(speak=True)
      })
    await self.execute_old_commands()
    await self.connect_to_waiting_room()
  
  async def create_lobby(self, index, members):
    index = str(index)
    lobby_role = await self.create_role(LOBBY_ROLE_PREFIX + index)
    overwrites = {
      self.guild.default_role: discord.PermissionOverwrite(
        connect = False, view_channel = False),
      self.get_manager_role(): discord.PermissionOverwrite(
        connect = True, view_channel = True),
      lobby_role: discord.PermissionOverwrite(
        connect = True, view_channel = True)
    }
    for member in members:
      await self.give_role(member, lobby_role)
    lobby = await self.create_voice_channel(
      LOBBY_NAME_PREFIX + index, self.get_tournament_category(), overwrites)
    return lobby

  async def delete_lobbies(self):
    if self.get_tournament_category():
      for channel in self.category_channel.channels:
        if LOBBY_NAME_PREFIX in channel.name:
          await self.delete_channel(channel, self.get_waiting_room())
    for role in self.guild.roles:
      if LOBBY_ROLE_PREFIX in role.name:
        await self.delete_if_exists(role)
  
  async def clean(self):
    await self.delete_lobbies()
    if self.get_tournament_category():
      for channel in self.category_channel.channels:
        await self.delete_channel(channel, self.get_chill_room())
      await self.delete_if_exists(self.category_channel)
    if self.get_manager_role():
      await self.delete_if_exists(self.manager_role)
    if self.get_participant_role():
      await self.delete_if_exists(self.participant_role)
    if self.get_banned_role():
      await self.delete_if_exists(self.banned_role)
    self.reset()
  
  def get_chill_room(self):
    self.chill_room = discord.utils.get(self.guild.channels, name=CHILL_ROOM_NAME)
    return self.chill_room
  
  def get_tournament_category(self):
    if not self.category_channel:
      self.category_channel = discord.utils.get(
        self.guild.channels,
        name=CATEGORY_CHANNEL_NAME)
    return self.category_channel
  
  def get_tournament_channel(self, name):
    category_channel = self.get_tournament_category()
    if category_channel:
      return discord.utils.get(category_channel.channels, name=name)

  def get_waiting_room(self):
    if not self.waiting_room:
      self.waiting_room = self.get_tournament_channel(WAITING_ROOM_NAME)
    return self.waiting_room
  
  def get_waiting_chat(self):
    if not self.waiting_chat:
      self.waiting_chat = self.get_tournament_channel(WAITING_CHAT_NAME)
    return self.waiting_chat
  
  def get_manager_role(self):
    if not self.manager_role:
      self.manager_role = self.get_role(MANAGER_ROLE_NAME)
    return self.manager_role
  
  def get_participant_role(self):
    if not self.participant_role:
      self.participant_role = self.get_role(PARTICIPANT_ROLE_NAME)
    return self.participant_role
  
  def get_banned_role(self):
    if not self.banned_role:
      self.banned_role = self.get_role(BANNED_ROLE_NAME)
    return self.banned_role
  
  async def give_participant_role(self, member):
    if self.get_banned_role() in member.roles:
      return False
    return await self.give_role(member, self.get_participant_role())

  async def give_manager_role(self, member):
    if self.get_banned_role() in member.roles:
      return False
    return await self.give_role(member, self.get_manager_role())
  
  async def give_banned_role(self, member):
    if await self.give_role(member, self.get_banned_role()):
      await self.revoke_manager_role(member, False)
      await self.revoke_participant_role(member)
      return True
    return False

  async def revoke_participant_role(self, member, move_to_waiting=True):
    if await self.revoke_role(member, self.get_participant_role()):
      for role in member.roles:
        if LOBBY_ROLE_PREFIX in role.name:
          await self.revoke_role(member, role)
          break
      if move_to_waiting and self.get_manager_role() not in member.roles:
        await self.maybe_move_from_lobby_to_waiting(member)
      return True
    return False

  async def revoke_manager_role(self, member, move_to_waiting=True):
    if await self.revoke_role(member, self.get_manager_role()):
      if move_to_waiting and self.get_manager_role() not in member.roles:
        await self.maybe_move_from_lobby_to_waiting(member)
      return True
    return False
  
  async def revoke_banned_role(self, member):
    return await self.revoke_role(member, self.get_banned_role())
  
  async def maybe_move_from_lobby_to_waiting(self, member):
      if member.voice and LOBBY_NAME_PREFIX in member.voice.channel.name:
        await self.move_member(member,
          at=self.get_tournament_category(),
          to=self.get_waiting_room(),
          force_mobile=True)
  
  def get_participants(self):
    return self.get_participant_role().members
  
  def get_managers(self):
    return self.get_manager_role().members

intents = discord.Intents.default()
intents.members = True # to get all the members of the guild at start-up
intents.presences = True # to know who is on mobile
client = CustomClient(guild_name=GUILD_NAME, intents=intents)
client.run(os.environ['DISCORD_TOKEN'])

'''
TODO:
- get rid of all get_* methods, instead set in the on_ready event method ?
- await entire for loop instead of single iterations
- test giving both participant and manager roles to someone
'''