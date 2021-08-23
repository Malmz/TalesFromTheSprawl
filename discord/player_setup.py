import discord
import asyncio
import simplejson
from configobj import ConfigObj
from enum import Enum
from typing import List

import players
import handles
import channels
import server
import finances
import groups
from custom_types import Handle, HandleTypes
from common import coin


# Known_handles is meant to be read-only during the event
# It can be edited manually
known_handles = ConfigObj('known_handles.conf')

class PlayerSetupInfo(object):
	def __init__(
		self,
		handle_id : str):
		self.handle_id = handle_id
		self.other_handles = [('__example_handle1', 0), ('__example_handle2', 0)]
		self.npc_handles = [('__example_npc1', 0), ('__example_npc1', 0)]
		self.burners = [('__example_burner1', 0), ('__example_burner1', 0)]
		self.groups = ['__example_group1', '__example_group2']
		self.shops = ['__example_shop1']
		self.starting_money = 10

	@staticmethod
	def from_string(string : str):
		obj = PlayerSetupInfo(None)
		obj.__dict__ = simplejson.loads(string)
		return obj

	def to_string(self):
		return simplejson.dumps(self.__dict__)

double_underscore = '__'

def add_known_handle(handle_id : str):
	if handle_id not in known_handles:
		known_handles[handle_id] = PlayerSetupInfo(handle_id).to_string()
		known_handles.write()
	else:
		print(f'Trying to edit player setup info for a handle that is already in the database. Please edit the file manually instead.')

def read_player_setup_info(handle_id : str):
	if handle_id in known_handles:
		return PlayerSetupInfo.from_string(known_handles[handle_id])


def reload_known_handles():
	global known_handles
	known_handles = ConfigObj('known_handles.conf')


async def player_setup_for_new_handle(handle : Handle):
	info = read_player_setup_info(handle.handle_id)
	reload_known_handles()
	if info is None:
		return None
	report = f'Loading known data for **{handle.handle_id}**...\n\n'
	if finances.can_have_finances(handle.handle_type):
		await finances.add_funds(handle, int(info.starting_money))
		report += f'Initial balance of **{handle.handle_id}**: {coin} **{info.starting_money}**\n\n'

	report += await setup_alternate_handles(handle, info.other_handles, HandleTypes.Regular)
	report += await setup_alternate_handles(handle, info.burners, HandleTypes.Burner)
	report += await setup_alternate_handles(handle, info.npc_handles, HandleTypes.NPC)

	report += await setup_groups(handle, info.groups)

	report += f'All data loaded. Welcome, **{handle.handle_id}**.'
	return report


async def setup_alternate_handles(main_handle, aliases, alias_type : HandleTypes):
	report = ''
	any_found = False
	for (other_handle_id, amount) in aliases:
		other_handle = await handles.create_handle(main_handle.actor_id, other_handle_id, alias_type)
		if other_handle.handle_type != HandleTypes.Unused:
			report += get_connected_alias_report(other_handle_id, alias_type, int(amount))
			await finances.add_funds(other_handle, int(amount))
			any_found = True
	if any_found:
		report += get_all_connected_aliases_of_type_report(alias_type)
	return report

def get_connected_alias_report(handle_id : str, handle_type : HandleTypes, amount : int):
	ending = '' if amount == 0 else f' with {coin} **{amount}**'
	if handle_type == HandleTypes.Regular:
		return f'- Connected alias: regular handle **{handle_id}**{ending}\n'
	elif handle_type == HandleTypes.Burner:
		return f'- Connected alias: burner handle **{handle_id}**{ending}\n'
	elif handle_type == HandleTypes.NPC:
		return f'  [OFF: added **{handle_id}** as an NPC handle{ending}.]\n'

def get_all_connected_aliases_of_type_report(handle_type : HandleTypes):
	if handle_type == HandleTypes.Regular:
		return '\n'
	elif handle_type == HandleTypes.Burner:
		return '  (Use \".burn <burner_name>\" to destroy a burner and erase its tracks)\n\n'
	elif handle_type == HandleTypes.NPC:
		return '  [OFF: NPC handles let you act as someone else, and cannot be traced to your other handles.]\n\n'


async def setup_groups(handle : Handle, group_names : List[str]):
	report = ''
	any_found = False
	guild = server.get_guild()
	for group_name in group_names:
		if double_underscore not in group_name:
			any_found = True
			await setup_group_for_new_member(guild, group_name, handle.actor_id)
			channel = groups.get_main_channel(group_name)
			report += f'- Confirmed group membership: {channels.clickable_channel_ref(channel)}\n'
	if any_found:
		report += '  Keep in mind that you can access your groups using all your handles.\n\n'
	return report

async def setup_group_for_new_member(guild, group_name : str, actor_id : str):
	if groups.group_exists(group_name):
		await groups.add_member_from_player_id(guild, group_name, actor_id)
	else:
		await groups.create_new_group(guild, group_name, [actor_id])
