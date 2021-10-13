import discord
import re

class BaseClient(discord.Client):
  
  def __init__(self, guild_name, intents=None):
    super().__init__(intents=intents)
    self.guild_name = guild_name
    self.guild = None
  
  def reset(self):
    self.category_channel = None
    self.waiting_chat = None
    self.waiting_room = None
    self.lobbies = None
    self.manager_role = None
    self.participant_role = None

  async def on_ready(self):
      self.guild = discord.utils.get(self.guilds, name=self.guild_name)
      print(f'{self.user} linked to {self.guild.name}')
  
  async def connect_to(self, channel):
    if channel.guild.voice_client:
      # can happen that guild.voice_client is not None and guild.me.voice is None
      if not channel.guild.me.voice or channel.guild.me.voice.channel != channel: 
        await channel.guild.voice_client.move_to(channel)
    else:
      await channel.connect(reconnect=True)
    #await channel.guild.change_voice_state(
    #  channel=channel, self_deaf=True, self_mute=True)
  
  async def move_member(self, member, to, at=None, force_mobile=False):
    if not self.is_faraway(member):
      # member is connected to this server, so can move it
      if member.voice.channel != to:
        # member isn't already in the destination channel
        if not at or member.voice.channel == at or member.voice.channel.category == at:
          # no condition on the current channel
          # or member is currently in the specified provenance channel
          if force_mobile or not \
              (member.is_on_mobile() or self.is_offline_or_invisible(member)):
            # Usually we don't move members on mobile as they'd get bugged
            # and invisible ones could be on mobile
            await member.move_to(to)
            return True
    return False
  
  async def check_valid_name(self, named_deletable_obj, name):
    if named_deletable_obj.name != name:
      await named_deletable_obj.delete()
      raise ValueError(
        f'{name} is not a valid name for a {named_deletable_obj.__class__.__name__}')
  
  async def create_role(self, name):
    role = await self.guild.create_role(name=name)
    await self.check_valid_name(role, name)
    #TODO color and category
    return role
  
  async def create_category_channel(self, name, overwrites=None):
    channel = await self.guild.create_category_channel(
        name=name, overwrites=overwrites)
    await self.check_valid_name(channel, name)
    return channel
  
  async def create_voice_channel(self, name, category=None, overwrites=None):
    channel = await self.guild.create_voice_channel(
        name=name, overwrites=overwrites, category=category)
    await self.check_valid_name(channel, name)
    return channel
  
  async def create_text_channel(self, name, category=None, overwrites=None):
    channel = await self.guild.create_text_channel(
        name=name, overwrites=overwrites, category=category)
    await self.check_valid_name(channel, name)
    return channel
  
  async def delete_if_exists(self, deletable):
    try:
      await deletable.delete()
      return True
    except discord.errors.NotFound:
      return False
  
  async def delete_channel(self, channel, backup_channel=None):
    if backup_channel and isinstance(channel, discord.VoiceChannel):
      for member in channel.members:
        await self.move_member(member, backup_channel, force_mobile=True)
    await self.delete_if_exists(channel)
  
  mention_re = re.compile("<@!?([0-9]{18})>")
  async def get_member(self, member_user_id_mention): #TODO test user not in guild
    if isinstance(member_user_id_mention, discord.Member):
      return member_user_id_mention
    if isinstance(member_user_id_mention, discord.User):
      member_user_id_mention = member_user_id_mention.id
    elif isinstance(member_user_id_mention, str):
      try:
        member_user_id_mention = int(member_user_id_mention)
      except ValueError:
          match = self.__class__.mention_re.match(member_user_id_mention)
          if match:
            member_user_id_mention = int(match.group(1))
          else:
            raise ValueError(f"{member_user_id_mention} isn't a valid member ID or mention")
    else:
      raise ValueError(f"member_user_id_mention should be a User or str")
    member = self.guild.get_member(member_user_id_mention)
    if not member: # member not cached
      member = await self.guild.fetch_member(member_user_id_mention)
      print(f'Fetched member {member}')
    return member
  
  async def refresh_mute(self, member):
    await member.move_to(member.voice.channel)
    #print(f'Forcing mute refresh of {member} in {member.voice.channel.name}')

  async def refresh_mute_role(self, member, role):
    if member.voice and not member.voice.channel.overwrites_for(role).is_empty():
      await self.refresh_mute(member)
  
  def get_role(self, name):
    return discord.utils.get(self.guild.roles, name=name)
  
  async def set_channel_permissions(self, channel, member_role, **permissions):
    current_overwrite = channel.overwrites_for(member_role)
    for perm, val in current_overwrite:
      if perm in permissions and permissions[perm] == val:
        del permissions[perm]
    if len(permissions) == 0:
      return False
    await channel.set_permissions(member_role, **permissions)
    #tasks = []
    for member in channel.members:
      if isinstance(member_role, discord.Member):
        if member_role == member:
          #tasks.append(asyncio.create_task(self.refresh_mute(member)))
          #tasks.append(self.refresh_mute(member))
          await self.refresh_mute(member)
      elif isinstance(member_role, discord.Role):
        if member_role in member.roles:
          #tasks.append(asyncio.create_task(self.refresh_mute(member)))
          #tasks.append(self.refresh_mute(member))
          await self.refresh_mute(member)
    #await asyncio.wait(tasks)
    #await asyncio.gather(*tasks)
    return True

  async def give_role(self, member, role):
    if role not in member.roles:
      await member.add_roles(role)
      await self.refresh_mute_role(member, role)
      return True
    return False
  
  async def revoke_role(self, member, role):
    if role in member.roles:
      await member.remove_roles(role)
      await self.refresh_mute_role(member, role)
      return True
    return False

  def is_faraway(self, member):
    return member.voice is None \
        or member.voice.channel is None \
        or member.voice.channel.guild != self.guild
  
  def is_offline_or_invisible(self, member):
    return member.status == discord.Status.offline

  async def close(self):
    for vc in self.voice_clients:
      await vc.disconnect()
    await self.change_presence(status=discord.Status.offline)
    await super().close()
