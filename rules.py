import sys
from traceback import print_exc
import random
import math
import discord
from constants import OK_REACTION, KO_REACTION, LOBBY_CAPACITY
from strings import *


class RuleProcessor:
  def __init__(self, *rules):
    self.rules = rules
  async def run(self, msg):
    for rule in self.rules:
      if await rule.process(msg): return True
    return False

########### Generic/Abstract Rules ###########

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
    self.cmd = cmd.upper()
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
      await msg.add_reaction(OK_REACTION)
      await super().execute(msg)
  async def on_execute_error(self, msg, e):
    print(f"Error while executing command {self.cmd}", file=sys.stderr)
    print_exc(file=sys.stdout)
    await msg.add_reaction(KO_REACTION)
  async def publish(self, embed):
    if self.client.get_waiting_chat():
      if isinstance(embed, str):
        embed = discord.Embed(description = embed)
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

########### Concrete Commands Rules ###########

class PrepareCmdRule(ProtectedCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_PREPARE)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      await self.client.prepare()
    await self.client.execute_old_commands()
    await super().execute(args, msg)

class CleanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_CLEAN)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      waiting_room = self.client.get_waiting_chat()
      await self.client.clean()
      if msg.channel != waiting_room:
        print(msg.channel, waiting_room)
        await super().execute(args, msg)

class PromoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_PROMOTE, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        await self.client.give_manager_role(member)
      await super().execute(args, msg)

class DemoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_DEMOTE, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        await self.client.revoke_manager_role(member)
      await super().execute(args, msg)

class BringCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_BRING, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        if await self.client.give_participant_role(member):
          await self.publish(MEMBER_JOINS.format(member=member.mention))
      await super().execute(args, msg)

class KickCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_KICK, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        if await self.client.revoke_participant_role(member):
          await self.publish(MEMBER_QUITS.format(member=member.mention))
      await super().execute(args, msg)

class BanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_BAN, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        if await self.client.give_banned_role(member):
          await self.publish(MEMBER_BANNED.format(member=member.mention))
      await super().execute(args, msg)

class UnbanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_UNBAN, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      for id_or_mention in args:
        member = await self.client.get_member(id_or_mention)
        if await self.client.revoke_banned_role(member):
          await self.publish(MEMBER_UNBANNED.format(member=member.mention))
      await super().execute(args, msg)

class BroadcastCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_BROADCAST, 1, math.inf)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      ad = msg.content[len(self.cmd)+1:]
      for member in self.client.get_participants():
        dm_channel = await member.create_dm()
        await dm_channel.send(ad)
      await super().execute(args, msg)

class SummonCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_SUMMON, 0, 1)
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and (len(args) == 0 or args[0] == "+")
       #and not self.client.is_lobby_phase()
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      do_all = len(args) == 1
      participants = self.client.get_participants()
      buffer_present = [SUMMON_ALREADY_HERE]
      buffer_summoned = [SUMMON_DONE]
      buffer_faraway = [SUMMON_DIDNT_FARAWAY]
      if do_all:
        buffer_mobile = [SUMMON_DONE_MOBILE]
        buffer_invisible = [SUMMON_DONE_INVISIBLE]
        buffer_busy = [SUMMON_DONE_BUSY]
      else:
        buffer_mobile = [SUMMON_DIDNT_MOBILE]
        buffer_invisible = [SUMMON_DIDNT_INVISIBLE]
        buffer_busy = [SUMMON_DIDNT_BUSY]
      buffer_error = [SUMMON_ERROR]
      
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
          buffer = buffer_mobile
        elif self.client.is_offline_or_invisible(participant):
          # Usually we don't move members with invisible status, as they could be on mobile
          buffer_invisible.append(participant.mention)
          if not do_all: continue
          buffer = buffer_invisible
        elif self.client.is_busy(participant):
          # Usually we don't move members in some known gaming channels
          buffer_busy.append(participant.mention)
          if not do_all: continue
          buffer = buffer_busy
        else:
          # member is ready to be summoned
          buffer_summoned.append(participant.mention)
          buffer = buffer_summoned
        try:
          await participant.move_to(self.client.get_waiting_room())
        except discord.errors.HTTPException as e:
          buffer[-1] = buffer[-1] + " ❌"
          # TODO as of now a participant could go in buffer_error and another buffer
          print(f"Member {participant} not connected to voice", file=sys.stderr)
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
          buffer_mobile + buffer_invisible + buffer_busy ))
      await super().execute(args, msg)

class MuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_MUTE)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      affected_channel = await self.client.mute_channel_managed_by(msg.author)
      if affected_channel:
        await self.publish(MUTED_CHANNED.format(channel=affected_channel.name))
      await super().execute(args, msg)

class UnmuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_UNMUTE)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      affected_channel = await self.client.mute_channel_managed_by(msg.author, unmute=True)
      if affected_channel:
        await self.publish(UNMUTED_CHANNED.format(channel=affected_channel.name))
      await super().execute(args, msg)

class StartCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_START, 0, 1)
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and (len(args) == 0 or args[0] == "+")
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      if self.client.is_lobby_phase():
        raise RuntimeError("Lobbies already created")
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
      
      buffer = [
        PARTICIPANTS_IN_CHANNEL.format(
          channel=self.client.get_waiting_room().name) + str(len(players)),
        PARTICIPANTS_IN_CHANNEL + str(len(absents)) ]
      for l in range(n_lobbies):
        players = lobbies[l]
        lobby_channel = await self.client.create_lobby(l+1, players)
        buffer.append(f'\n**Lobby {l+1}**: *{len(players)}*')
        for member in players:
          if member.is_on_mobile():
            # We usually don't move members on mobile as they'd get bugged...
            buffer.append(MEMBER_MOBILE.format(member=member.mention))
            if not do_all: continue
          elif self.client.is_offline_or_invisible(member):
            # ...and invisible ones could be on mobile!
            buffer.append(MEMBER_INVISIBLE.format(member=member.mention))
            if not do_all: continue
          else:
            buffer.append(member.mention)
          try:
            await member.move_to(lobby_channel)
          except discord.errors.HTTPException as e:
            buffer[-1] = MEMBER_INVISIBLE.format(member=buffer[-1])
            print(f"Member {member} not connected to voice", file=sys.stderr)
            print(e)

      await self.publish('\n'.join(buffer))
      await super().execute(args, msg)

class EndCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_END)
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      if not self.client.is_lobby_phase():
        raise RuntimeError("There are no lobbies")
      await self.client.delete_lobbies()
      await super().execute(args, msg)

class JoinCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_JOIN)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      member = await self.client.get_member(msg.author)
      if await self.client.give_participant_role(member):
        await self.publish(MEMBER_JOINS.format(member=member.mention))
      await super().execute(args, msg)

class QuitCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_QUIT)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      member = await self.client.get_member(msg.author)
      if await self.client.revoke_participant_role(member):
        await self.publish(MEMBER_QUITS.format(member=member.mention))
      await super().execute(args, msg)

class ListCmdRule(WaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_LIST)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      participants = self.client.get_participants()
      buffer = []
      for member in participants:
        buffer.append(str(member))
      buffer[0] = N_PARTICPANTS.format(n_participants=len(participants)) + buffer[0]
      await self.publish(", ".join(buffer))
      await super().execute(args, msg)

class TerminateCmdRule(ProtectedCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_TERMINATE)
  async def execute(self, args, msg):
    await super().execute(args, msg)
    await self.client.close()
