import discord
import random
import math
from config import OK_REACTION, KO_REACTION, LOBBY_CAPACITY
import sys

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
    #if not msg.author.bot:
    if msg.author != self.client.user:
      if msg.content != "":
        args = msg.content.upper().split()
        cmd = args[0]
        args = args[1:]
        if await self.evaluate(cmd, args, msg):
          async with msg.channel.typing():
            try: await self.execute(args, msg)
            except Exception as e: await self.on_execute_error(msg, e)
          return True
      return False
  async def evaluate(self, cmd, args, msg):
    if await super().evaluate(msg):
      if cmd == self.cmd:
        return self.min_args <= len(args) <= self.max_args
    return False
  async def execute(self, args, msg):
      try: await msg.add_reaction(OK_REACTION)
      except discord.errors.NotFound: pass
      await super().execute(msg)
  async def on_execute_error(self, msg, e):
    print(f"Error while executing command {msg.content}", file=sys.stderr)
    print(e)
    await msg.add_reaction(KO_REACTION)
  async def publish(self, embed):
    if self.client.get_waiting_chat():
      if isinstance(embed, str):
        embed = discord.Embed(description = embed)
      try:
        await self.client.get_waiting_chat().send(embed=embed)
      except discord.errors.NotFound as e:
        print(f"404 Waiting Room", file=sys.stderr)
        print(e)

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

class PrepareCmdRule(ProtectedCmdRule):
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
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and (len(args) == 0 or args[0] == "+")
       #and not self.client.is_lobby_phase()
  async def execute(self, args, msg):
    do_all = len(args) == 1
    participants = self.client.get_participants()
    buffer_present = ["**Already here**: "]
    buffer_summoned = ["\n**Ready for summon**: "]
    buffer_faraway = ["\n**Couldn't summon because far away**: "]
    if do_all:
      buffer_mobile = ["\n**Summoned even if on mobile**: "]
      buffer_invisible = ["\n**Summoned even if invisible**: "]
      buffer_busy = ["\n**Summoned even if busy**:"]
    else:
      buffer_mobile = ["\n**Not summoned because on mobile**: "]
      buffer_invisible = ["\n**Not summoned because invisible**: "]
      buffer_busy = ["\n**Not summoned because busy**:"]
    buffer_error = ["\n**Couldn't summon because of some error**: "]
    
    for participant in participants:
      if self.client.is_faraway(participant):
        # member isn't connected to this server
        buffer_faraway.append(participant.mention)
        continue
      elif self.client.is_waiting(participant):
        # member is already in the waiting-room
        buffer_present.append(participant.mention)
        continue
      elif participant.is_on_mobile():
        # Usually we don't move members on mobile, as they'd get bugged
        buffer_mobile.append(participant.mention)
        if not do_all: continue
      elif self.client.is_offline_or_invisible(participant):
        # Usually we don't move members with invisible status, as they could be on mobile
        buffer_invisible.append(participant.mention)
        if not do_all: continue
      elif self.client.is_busy(participant):
        # Usually we don't move members in some known gaming channels
        buffer_busy.append(participant.mention)
        if not do_all: continue
      else:
        # member is ready to be summoned
        buffer_summoned.append(participant.mention)
      try:
        await participant.move_to(self.client.get_waiting_room())
      except discord.errors.HTTPException as e:
        buffer_error.append(participant.mention)
        # TODO as of now a participant could go in buffer_error and another buffer
        print(f"Member {participant} not connected to voice channel", file=sys.stderr)
        print(e)
    
    buffer_present[0] += str(len(buffer_present) - 1)
    buffer_summoned[0] += str(len(buffer_summoned) - 1)
    buffer_faraway[0] += str(len(buffer_faraway) - 1)
    buffer_mobile[0] += str(len(buffer_mobile) - 1)
    buffer_invisible[0] += str(len(buffer_invisible) - 1)
    buffer_busy[0] += str(len(buffer_busy) - 1)
    buffer_error[0] += str(len(buffer_error) - 1)
    await self.publish("\n".join(
        buffer_present + buffer_summoned + buffer_faraway + \
        buffer_mobile + buffer_invisible + buffer_busy + \
        buffer_error ))
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
    affected_channel = await self.client.mute_channel_managed_by(msg.author, unmute=True)
    if affected_channel:
      await self.publish(f'Unmuted {affected_channel.name}')
    await super().execute(args, msg)

class StartCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "START", 0, 1)
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and (len(args) == 0 or args[0] == "+") \
       and not self.client.is_lobby_phase()
  async def execute(self, args, msg):
    do_all = len(args) == 1

    waiters = set(self.client.get_waiting_room().members)
    participants = set(self.client.get_participants())
    players = participants.intersection(waiters)
    absents = participants.difference(waiters)

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
    
    buffer = [f'Participants in {self.client.get_waiting_room().name}: {len(players)}',
              f'Participants missing: {len(absents)}']
    for l in range(n_lobbies):
      players = lobbies[l]
      lobby_channel = await self.client.create_lobby(l+1, players)
      buffer.append(f'\n**Lobby {l+1}**: *{len(players)}*')
      for member in players:
        if member.is_on_mobile() or self.client.is_offline_or_invisible(member):
          # We usually don't move members on mobile as they'd get bugged
          # and invisible ones could be on mobile
          buffer.append(f'{member.mention} on 📱 or 👻')
          if not do_all: continue
        else:
          buffer.append(member.mention)
        try:
          await member.move_to(lobby_channel)
        except discord.errors.HTTPException as e:
          buffer[-1] = buffer[-1] + ' ❌'
          print(f"Member {member} not connected to voice", file=sys.stderr)
          print(e)

    await self.publish('\n'.join(buffer))
    await super().execute(args, msg)

class EndCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "END")
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and self.client.is_lobby_phase()
  async def execute(self, args, msg):
    await self.client.delete_lobbies()
    await super().execute(args, msg)

class CleanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "CLEAN")
  async def execute(self, args, msg):
    await self.client.clean()
    await super().execute(args, msg)

class TerminateCmdRule(ProtectedCmdRule):
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

class ListCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, "LIST")
  async def execute(self, args, msg):
    participants = self.client.get_participants()
    buffer = []
    for member in participants:
      buffer.append(str(member))
    buffer[0] = f'{len(participants)} participants:\n' + buffer[0]
    await self.publish(", ".join(buffer))
    await super().execute(args, msg)