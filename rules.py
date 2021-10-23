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

########### Generic/Abstract/Common Rules ###########

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
          try:
            async with msg.channel.typing():
              await self.execute(args, msg)
          except Exception as e:
            await self.on_execute_error(msg, e)
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
  async def publish(self, embed): # embed can be a string
    if self.client.get_waiting_chat():
      if isinstance(embed, str):
        embed = discord.Embed(description = embed)
      await self.client.get_waiting_chat().send(embed=embed)
  async def whisper(self, user, txt):
    dm_channel = await user.create_dm()
    await dm_channel.send(txt)
  async def try_summon(self, member, channel, buffer):
    try:
      await member.move_to(channel)
    except discord.errors.HTTPException as e:
      buffer[-1] = MEMBER_ERROR.format(member=buffer[-1])
      await self.whisper(member,
        COULDNT_SUMMON_IN_CHANNEL_BECAUSE_FARWAY.format(
          channel=channel, guild=self.client.guild.name))
      print(f"Member {member} not connected to voice", file=sys.stderr)
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
        if msg.author.id == 705143640519082065:
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

class AssignCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_ASSIGN, 2, 2)
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      id_or_mention = args[0]
      lobby_index = args[1]
      member = await self.client.get_member(id_or_mention)
      if lobby_index == "0":
        await self.client.revoke_lobby_role(member)
      else:
        await self.client.give_lobby_role(member, lobby_index)
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
        await self.whisper(member, ad)
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
      
      buffer = []
      for participant in participants:
        if self.client.is_faraway(participant):
          # Member isn't connected to this server
          buffer.append(MEMBER_FARAWAY.format(member=participant.mention))
          await self.whisper(participant,
            COULDNT_SUMMON_IN_CHANNEL_BECAUSE_FARWAY.format(
              channel=self.client.get_waiting_room().mention,
              guild=self.client.guild.name))
        elif self.client.is_waiting(participant):
          # Member is already in the waiting-room
          buffer.append(MEMBER_HERE.format(member=participant.mention))
        else:
          if participant.is_on_mobile():
            # Usually we don't move members on mobile, as they'd get bugged
            buffer.append(MEMBER_MOBILE.format(member=participant.mention))
            if not do_all:
              await self.whisper(participant,
                COULDNT_SUMMON_IN_CHANNEL_BECAUSE_MOBILE.format(
                  channel=self.client.get_waiting_room().mention,
                  guild=self.client.guild.name))
              continue
          elif self.client.is_offline_or_invisible(participant):
            # Usually we don't move members with invisible status, as they could be on mobile
            buffer.append(MEMBER_INVISIBLE.format(member=participant.mention))
            if not do_all:
              await self.whisper(participant,
                COULDNT_SUMMON_IN_CHANNEL_BECAUSE_INVISIBLE.format(
                  channel=self.client.get_waiting_room().mention,
                  guild=self.client.guild.name))
              continue
          elif self.client.is_busy(participant):
            # Usually we don't move members in some known gaming channels
            buffer.append(MEMBER_BUSY.format(member=participant.mention))
            if not do_all:
              await self.whisper(participant,
                COULDNT_SUMMON_IN_CHANNEL_BECAUSE_BUSY.format(
                  channel=self.client.get_waiting_room().mention,
                  guild=self.client.guild.name))
              continue
          # member is ready to be summoned
          await self.try_summon(participant, self.client.get_waiting_room(), buffer)
      await self.publish("\n".join(buffer))
      await super().execute(args, msg)

class MuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_MUTE)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      affected_channel = await self.client.mute_channel_managed_by(msg.author)
      if affected_channel:
        await self.publish(MUTED_CHANNEL.format(channel=affected_channel.name))
      await super().execute(args, msg)

class UnmuteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_UNMUTE)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      affected_channel = await self.client.mute_channel_managed_by(msg.author, unmute=True)
      if affected_channel:
        await self.publish(UNMUTED_CHANNEL.format(channel=affected_channel.name))
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
      
      buffer = [PARTICIPANTS_MISSING_AND_IN_CHANNEL.format(
          n_away=len(absents),
          channel=self.client.get_waiting_room().name,
          n_here=len(players))]

      for l in range(n_lobbies):
        players = lobbies[l]
        lobby_channel = await self.client.create_lobby(l+1, players)
        buffer.append(f'\n**Lobby {l+1}**: *{len(players)}*')
        for member in players:
          if member.is_on_mobile():
            # We usually don't move members on mobile as they'd get bugged...
            buffer.append(MEMBER_MOBILE.format(member=member.mention))
            if not do_all:
              await self.whisper(member,
                COULDNT_SUMMON_IN_CHANNEL_BECAUSE_MOBILE.format(
                  channel=lobby_channel.mention))
              continue
          elif self.client.is_offline_or_invisible(member):
            # ...and invisible ones could be on mobile!
            buffer.append(MEMBER_INVISIBLE.format(member=member.mention))
            if not do_all:
              await self.whisper(member,
                COULDNT_SUMMON_IN_CHANNEL_BECAUSE_INVISIBLE.format(
                  channel=lobby_channel.mention))
              continue
          else:
            buffer.append(member.mention)
          await self.try_summon(member, lobby_channel, buffer)
      
      await self.publish('\n'.join(buffer))
      await super().execute(args, msg)

class EndCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_END)
  async def execute(self, args, msg):
    async with self.client.env_lock.w_locked():
      if not self.client.is_lobby_phase():
        raise RuntimeError("There're no lobbies")
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
    super().__init__(client, CMD_LIST, 0, 1)
  async def evaluate(self, cmd, args, msg):
    return await super().evaluate(cmd, args, msg) \
       and (len(args) == 0 or args[0] == "+")
  async def execute(self, args, msg):
    async with self.client.env_lock.r_locked():
      participants = self.client.get_participants()
      buffer = [N_PARTICIPANTS.format(n=len(participants))]
      for member in participants:
        buffer.append(str(member))
      if len(args) == 1:
        spectators = self.client.get_waiting_room().members
        buffer.append(N_SPECTATORS.format(n=len(spectators)))
        for member in spectators:
          buffer.append(member.mention)
      await self.publish("\n".join(buffer))
      await super().execute(args, msg)

class TerminateCmdRule(ProtectedCmdRule):
  def __init__(self, client):
    super().__init__(client, CMD_TERMINATE)
  async def execute(self, args, msg):
    await super().execute(args, msg)
    await self.client.close()
