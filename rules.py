import discord
import random
import math
from config import OK_REACTION, LOBBY_CAPACITY

class MessageRule:
  def __init__(self, client):
    self.client = client
  async def process(self, msg):
    if await self.evaluate(msg):
      await self.execute(msg)
  async def evaluate(self, msg): return True
  async def execute(self, msg): pass

class DirectMessageRule(MessageRule):
  async def evaluate(self, msg):
    if await super().evaluate(msg):
      return isinstance(msg.channel, discord.channel.DMChannel)

class LogDirectMessageRule(DirectMessageRule):
  async def evaluate(self, msg):
    if await super().evaluate(msg):
      if msg.author == self.client.user:
        print(f'DM to {msg.channel.recipient}: <<\n{msg.content}\n>>')
      else:
        print(f'DM from {msg.author}: <<\n{msg.content}\n>>')
    return False

class CmdRule(MessageRule):
  def __init__(self, client, cmd, min_args=0, max_args=0):
    super().__init__(client)
    self.cmd = cmd
    self.min_args = min_args
    self.max_args = max_args
  async def process(self, msg):
    if msg.author != self.client.user:
      args = msg.content.upper().split()
      try: # DEBUG
        cmd = args[0]
      except Exception as e:
        print(self.__class__.name)
        print(msg)
        print(msg.content)
        raise e
      args = args[1:]
      if await self.evaluate(cmd, args, msg):
        async with msg.channel.typing():
          await self.execute(args, msg)
  async def evaluate(self, cmd, args, msg):
    if await super().evaluate(msg):
      if cmd == self.cmd:
        return self.min_args <= len(args) <= self.max_args
    return False
  async def execute(self, args, msg):
      try: await msg.add_reaction(OK_REACTION)
      except discord.errors.NotFound: pass
      await super().execute(msg)
  async def publish(self, s):
    if self.client.get_waiting_chat():
      embed = discord.Embed()
      embed.description = s
      await self.client.get_waiting_chat().send(embed=embed)

class ProtectedCmdRule(CmdRule):
  async def evaluate(self, cmd, args, msg):
    if await super().evaluate(cmd, args, msg):
      member = await self.client.get_member(msg.author)
      if member:
        if member.guild_permissions.administrator:
          return True
        if self.client.get_manager_role() in member.roles:
          return True
    return False

class WaitingChatCmdRule(CmdRule):
  async def evaluate(self, cmd, args, msg):
    if await super().evaluate(cmd, args, msg):
      if isinstance(msg.channel, discord.channel.TextChannel):
        return msg.channel == self.client.get_waiting_chat()
      if isinstance(msg.channel, discord.channel.DMChannel):
        return (await self.client.get_member(msg.author)) != None
    return False

class ProtectedWaitingChatCmdRule(ProtectedCmdRule):
  async def evaluate(self, cmd, args, msg):
    if await super().evaluate(cmd, args, msg):
      if isinstance(msg.channel, discord.channel.TextChannel):
        return msg.channel == self.client.get_waiting_chat()
      if isinstance(msg.channel, discord.channel.DMChannel):
        return (await self.client.get_member(msg.author)) != None
    return False

class PrepareCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "PREPARE")
  async def execute(self, args, msg):
    await self.client.prepare()
    await super().execute(args, msg)

class PromoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "PROMOTE", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      await self.client.give_manager_role(member)
    await super().execute(args, msg)

class DemoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "DEMOTE", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      await self.client.revoke_manager_role(member)
    await super().execute(args, msg)

class BringCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "BRING", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      if await self.client.give_participant_role(member):
        await self.publish(f'{member.mention} joins the tournament')
    await super().execute(args, msg)

class KickCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "KICK", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      if await self.client.revoke_participant_role(member):
        await self.publish(f'{member.mention} quits the tournament')
    await super().execute(args, msg)

class BanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "BAN", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      if await self.client.give_banned_role(member):
        await self.publish(f'{member.mention} banned from tournament')
    await super().execute(args, msg)

class UnbanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "UNBAN", 1, math.inf)
  async def execute(self, args, msg):
    for id_or_mention in args:
      member = await self.client.get_member(id_or_mention)
      if await self.client.revoke_banned_role(member):
        await self.publish(f'{member.mention} unbanned from tournament')
    await super().execute(args, msg)

class BroadcastCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "BROADCAST", 1, math.inf)
  async def execute(self, args, msg):
    ad = msg.content[len(self.cmd)+1:]
    for member in self.client.get_participants():
      dm_channel = await member.create_dm()
      await dm_channel.send(ad)
    await super().execute(args, msg)

class SummonCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "SUMMON", 0, 1)
  async def execute(self, args, msg):
    do_all = False
    if len(args) == 1:
      if args[0] == "ALL":
        do_all = True
      else:
        return False
    participants = self.client.get_participants()
    buffer_ko = ["**Couldn't summon because far away**: "]
    buffer_present = ["**Already here**: "]
    buffer_ok = ["**Summoned**: "]
    if do_all:
      buffer_mobile = ["**Summoned even if invisible or on mobile**: "]
    else:
      buffer_mobile = ["**Not summoned because invisible or on mobile**: "]
    for participant in participants:
      if participant.voice and participant.voice.channel.guild == self.client.guild:
        # member is connected to this server
        if participant.voice.channel != self.client.get_waiting_room():
          # member isn't waiting in the waiting room
          if participant.is_on_mobile() or participant.status == discord.Status.offline:
            # Usually we don't move members on mobile as they'd get bugged
            buffer_mobile.append(participant.mention)
            if do_all:
              await participant.move_to(self.client.get_waiting_room())
          else:
            buffer_ok.append(participant.mention)
            await participant.move_to(self.client.get_waiting_room())
        else:
          # member is waiting in the waiting room
          buffer_present.append(participant.mention)
      else:
        # member isn't connected to this server
        buffer_ko.append(participant.mention)
    buffer_ok[0] += str(len(buffer_ok) - 1)
    buffer_ko[0] += str(len(buffer_ko) - 1)
    buffer_present[0] += str(len(buffer_present) - 1)
    buffer_mobile[0] += str(len(buffer_mobile) - 1)
    await self.publish("\n".join(
        buffer_ko + buffer_present + buffer_ok + buffer_mobile))
    await super().execute(args, msg)

class MuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "MUTE")
  async def execute(self, args, msg):
    affected_channel = await self.client.mute_channel_managed_by(msg.author)
    if affected_channel:
      await self.publish(f'Muted {affected_channel.name}')
    await super().execute(args, msg)

class UnmuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "UNMUTE")
  async def execute(self, args, msg):
    channel = await self.client.mute_channel_managed_by(msg.author, unmute=True)
    if channel:
      await self.publish(f'Unmuted {channel.name}')
    await super().execute(args, msg)

class StartCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "START")
  async def execute(self, args, msg):
    await self.client.delete_lobbies()
    
    waiters = set(self.client.get_waiting_room().members)
    participants = set(self.client.get_participants())
    players = participants.intersection(waiters)
    absents = participants.difference(waiters)

    buffer = []
    buffer.append(f'Participants **not here**: *{len(absents)}*')
    buffer.append(f'Participants **waiting**: *{len(players)}*')

    print('members:', len(self.client.guild.members))
    print('waiters:', len(waiters))
    print('participants:', len(participants))

    players = list(players)
    random.shuffle(players)
    n_lobbies = (len(players) + LOBBY_CAPACITY - 1) // LOBBY_CAPACITY
    lobbies = [[] for _ in range(n_lobbies)]
    for p in range(len(players)):
      lobby = lobbies[p % n_lobbies]
      member = players[p]
      lobby.append(member)

    for l in range(n_lobbies):
      players = lobbies[l]
      lobby_channel = await self.client.create_lobby(l+1, players)
      buffer.append(f'**Lobby {l+1}**: *{len(players)}*')
      for member in players:
        if member.is_on_mobile():
          # We don't move members on mobile as they'd get bugged
          buffer.append(f'{member.mention} on **mobile**, move by yourself!')
        else:
          await member.move_to(lobby_channel)
          buffer.append(member.mention)

    await self.publish('\n'.join(buffer))
    await super().execute(args, msg)

class EndCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "END")
  async def execute(self, args, msg):
    await self.client.delete_lobbies()
    await super().execute(args, msg)

class CleanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "CLEAN")
  async def execute(self, args, msg):
    await self.client.clean()
    await super().execute(args, msg)

class TerminateCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "TERMINATE")
  async def execute(self, args, msg):
    await super().execute(args, msg)
    await self.client.close()

class JoinCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "JOIN")
  async def execute(self, args, msg):
    member = await self.client.get_member(msg.author)
    if await self.client.give_participant_role(member):
      await self.publish(f'{member.mention} joins the tournament')
    await super().execute(args, msg)

class QuitCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "QUIT")
  async def execute(self, args, msg):
    member = await self.client.get_member(msg.author)
    if await self.client.revoke_participant_role(member):
      await self.publish(f'{member.mention} quits the tournament')
    await super().execute(args, msg)