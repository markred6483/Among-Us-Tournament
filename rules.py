import discord
import random
import math
from config import OK_REACTION, LOBBY_CAPACITY

class MessageRule:
  def __init__(self, client):
    self.client = client
  async def process(self, msg):
    return True

class DirectMessageRule(MessageRule):
  async def process(self, msg):
    if await super().process(msg):
      return isinstance(msg.channel, discord.channel.DMChannel)

class LogDirectMessageRule(DirectMessageRule):
  async def process(self, msg):
    if await super().process(msg):
      if msg.author == self.client.user:
        print(f'DM to {msg.channel.recipient}: <<\n{msg.content}\n>>')
      else:
        print(f'DM from {msg.author}: <<\n{msg.content}\n>>')
    return False

class CmdRule(MessageRule):
  def __init__(self, client, min_args=0, max_args=0):
    super().__init__(client)
    self.min_args = min_args
    self.max_args = max_args
  async def publish(self, s):
    if self.client.get_waiting_chat():
      await self.client.get_waiting_chat().send(s)
  async def process(self, msg):
    if await super().process(msg):
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
        if self.min_args <= len(args) <= self.max_args:
          if await self.execute(cmd, args, msg):
            try: await msg.add_reaction(OK_REACTION)
            except discord.errors.NotFound: pass
            return True
    return False
  async def execute(self, cmd, args, msg):
    return True

class ProtectedCmdRule(CmdRule):
  def __init__(self, client, min_args=0, max_args=0):
    super().__init__(client, min_args, max_args)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      member = await self.client.get_member(msg.author)
      if member.guild_permissions.administrator:
        return True
      if self.client.get_manager_role() in member.roles:
        return True
    return False
  
class WaitingChatCmdRule(CmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if isinstance(msg.channel, discord.channel.TextChannel):
        return msg.channel == self.client.get_waiting_chat()
      if isinstance(msg.channel, discord.channel.DMChannel):
        return (await self.client.get_member(msg.author)) != None
    return False

class ProtectedWaitingChatCmdRule(ProtectedCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if isinstance(msg.channel, discord.channel.TextChannel):
        return msg.channel == self.client.get_waiting_chat()
      if isinstance(msg.channel, discord.channel.DMChannel):
        return (await self.client.get_member(msg.author)) != None
    return False

class PrepareCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "PREPARE":
        await self.client.prepare()
        return True
    return False

class PromoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "PROMOTE":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          await self.client.give_manager_role(member)
        return True
      return False

class DemoteCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "DEMOTE":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          await self.client.revoke_manager_role(member) 
        return True
      return False

class BringCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "BRING":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          if await self.client.give_participant_role(member):
            await self.publish(f'{member.mention} joins the tournament')
        return True
      return False

class KickCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "KICK":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          if await self.client.revoke_participant_role(member):
            await self.publish(f'{member.mention} quits the tournament')
        return True
      return False

class BanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "BAN":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          if await self.client.give_banned_role(member):
            await self.publish(f'{member.mention} banned from tournament')
        return True
      return False

class UnbanCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "UNBAN":
        for id_or_mention in args:
          member = await self.client.get_member(id_or_mention)
          if await self.client.revoke_banned_role(member):
            await self.publish(f'{member.mention} unbanned from tournament')
        return True
      return False

class SummonCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 0, 1)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "SUMMON":
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
        return True
    return False

class BroadcastCmdRule(ProtectedWaitingChatCmdRule):
  def __init__(self, client):
    super().__init__(client, 1, math.inf)
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      EXPECTED_CMD = "BROADCAST"
      if cmd == EXPECTED_CMD:
        ad = msg.content[len(EXPECTED_CMD)+1:]
        for member in self.client.get_participants():
          dm_channel = await member.create_dm()
          await dm_channel.send(ad)
        return True
    return False

class MuteCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "MUTE":
        affected_channel = await self.client.mute_channel_managed_by(msg.author)
        if affected_channel:
          await self.publish(f'Muted {affected_channel.name}')
        return True
    return False

class UnmuteCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "UNMUTE":
        channel = await self.client.mute_channel_managed_by(msg.author, unmute=True)
        if channel:
          await self.publish(f'Unmuted {channel.name}')
        return True
    return False

class StartCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "START":
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

        await msg.channel.send('\n'.join(buffer))

        return True
    return False

class EndCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "END":
        await self.client.delete_lobbies()
        return True
    return False

class CleanCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "CLEAN":
        await self.client.clean()
        return True
    return False

class TerminateCmdRule(ProtectedWaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "TERMINATE":
        await self.client.close()
        return True
    return False

class JoinCmdRule(WaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "JOIN":
        member = await self.client.get_member(msg.author)
        if await self.client.give_participant_role(member):
          await self.publish(f'{member.mention} joins the tournament')
        return True
    return False

class QuitCmdRule(WaitingChatCmdRule):
  async def execute(self, cmd, args, msg):
    if await super().execute(cmd, args, msg):
      if cmd == "QUIT":
        member = await self.client.get_member(msg.author)
        if await self.client.revoke_participant_role(member):
          await self.publish(f'{member.mention} quits the tournament')
        return True
    return False

'''
TODO:
- split process method in two methods: evaluate and ...
  - async with channel.typing() in CmdRule

'''