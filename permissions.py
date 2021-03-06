import discord
import sys

def banned(tournament):
  return tournament.get_banned_role()

def manager(tournament):
  return tournament.get_manager_role()

def participant(tournament):
  return tournament.get_participant_role()

def default(tournament):
  return tournament.guild.default_role

def verified(tournament):
  return tournament.get_verified_role()

def diff(role, overwrite):
  if role is None:
    return overwrite
  allow, deny = overwrite.pair()
  delta = ~role.permissions.value & allow.value
  if delta != 0:
    delta = discord.Permissions(delta)
    buffer = []
    for perm, val in delta:
      if val: buffer.append(perm)
    print(f"{role} should permit {', '.join(buffer)}", file=sys.stderr)
    # raise RuntimeError(f"{role} should permit {', '.join(buffer)}")
  return discord.PermissionOverwrite.from_pair(discord.Permissions(0), deny)

def get_category_overwrites(tournament):
  return None

def get_chat_overwrites(tournament):
  base_overwrite = discord.PermissionOverwrite(
    view_channel=True, send_messages=True)
  return {
    default(tournament): diff(verified(tournament), base_overwrite),
    banned(tournament): discord.PermissionOverwrite(
        send_messages=False ),
    manager(tournament): discord.PermissionOverwrite(
        manage_messages=True ),
  }

def get_room_overwrites(tournament):
  base_overwrite = discord.PermissionOverwrite(
     view_channel=True, connect=True, speak=False)
  return {
    default(tournament): diff(verified(tournament), base_overwrite),
    participant(tournament): discord.PermissionOverwrite(
        speak=True ),
    manager(tournament): discord.PermissionOverwrite(
        speak=True ),
    banned(tournament): discord.PermissionOverwrite(
        connect=False ),
  }

def get_lobby_overwrites(tournament, lobby_role):
  base_overwrite = discord.PermissionOverwrite(
     view_channel=False)
  return {
    default(tournament): diff(verified(tournament), base_overwrite),
    manager(tournament): discord.PermissionOverwrite(
        view_channel=True, speak=True ),
    lobby_role: discord.PermissionOverwrite(
        view_channel=True ),
  }

  