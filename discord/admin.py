import actors
import players
import groups
import channels
import server

from discord.ext import commands
import discord
import asyncio
import random

### Module admin.py
# This module holds the admin cog, which is used to


# TODO: change these to be admin-only (currently they are actually GM-only)
# TODO: grab the name of the admin role from env file

class AdminCog(commands.Cog, name='admin'):
	"""Admin-only commands, hidden by default. To view documentation, use \"help <command>\". The commands are:
	init_all_players, fake_join, fake_join_name, fake_join_nick, clear_all_players, clear_all_actors, clear_actor, ping"""
	def __init__(self, bot):
		self.bot = bot
		self._last_member = None
		self.join_semaphore = None

	# Admin-only commands for testing etc.

	@commands.command(
		name='init_all_players',
		help='Admin-only. Initialise all current members of the server as players.',
		hidden=True
		)
	@commands.has_role('gm')
	async def init_all_players_command(self, ctx):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		await players.initialise_all_users()
		await ctx.send('Done.')

	@commands.command(
		name='fake_join',
		help='Admin-only. Initialise a user as a player.',
		hidden=True)
	@commands.has_role('gm')
	async def fake_join_command(self, ctx, user_id, handle : str=None):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		member_to_fake_join = await ctx.guild.fetch_member(user_id)
		if member_to_fake_join is None:
			await ctx.send(f'Failed: member with user_id {user_id} not found.')
		elif handle is None:
			await ctx.send(f'Failed: you must give the player\'s main handle.')
		else:
			report = await players.create_player(member_to_fake_join, handle)
			if report is None:
				report = "Done."
			await ctx.send(report)

	@commands.command(
		name='fake_join_name',
		help='Admin-only. Initialise a user as a player (based on discord name).',
		hidden=True)
	@commands.has_role('gm')
	async def fake_join_name_command(self, ctx, name : str, handle : str=None):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		members = await ctx.guild.fetch_members(limit=100).flatten()
		member_to_fake_join = discord.utils.find(lambda m: m.name == name, members)
		if member_to_fake_join is None:
			await ctx.send(f'Failed: member with name {name} not found.')
		elif handle is None:
			await ctx.send(f'Failed: you must give the player\'s main handle.')
		else:
			report = await players.create_player(member_to_fake_join, handle)
			if report is None:
				report = "Done."
			await ctx.send(report)

	@commands.command(
		name='fake_join_nick',
		help='Admin-only. Initialise a user as a player (based on server nick).',
		hidden=True)
	@commands.has_role('gm')
	async def fake_join_nick_command(self, ctx, nick : str, handle : str=None):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		member_to_fake_join = await server.get_member_from_nick(nick)
		if member_to_fake_join is None:
			await ctx.send(f'Failed: member with nick {nick} not found.')
		elif handle is None:
			await ctx.send(f'Failed: you must give the player\'s main handle.')
		else:
			report = await players.create_player(member_to_fake_join, handle)
			if report is None:
				report = "Done."
			await ctx.send(report)

	# This command ONLY works in the landing page channel.
	# Note: no other commands work in the landing page channel!
	# TODO: semaphore for joining
	@commands.command(
		name='join',
		help='Claim a handle and join the game. Only for players who have not yet joined.',
		hidden=True)
	async def join_command(self, ctx, handle_id : str=None):
		allowed = await channels.pre_process_command(ctx, allow_cmd_line=False, allow_landing_page=True)
		if not allowed:
			return
		member = await ctx.guild.fetch_member(ctx.message.author.id)
		if member is None:
			await self.send_response_in_landing_page(ctx, 'Failed: member not found.')
		elif handle_id is None or handle_id == 'handle' or handle_id == '<handle>':
			await self.send_response_in_landing_page(ctx, '```You must say which handle is yours! Example: \".join shadow_weaver\"``')
		else:
			sem_id = await self.get_join_semaphore(str(member.id))
			if sem_id is None:
				await self.send_response_in_landing_page(ctx, '```Failed: system is too busy. Wait a few minutes and try again.``')
			else:
				report = await players.create_player(member, handle_id)
				if report is not None:
					await self.send_response_in_landing_page(ctx, f'```Failed: invalid starting handle \"{handle_id}\" (or handle is already taken).```')
				else:
					await server.swallow(ctx.message, alert=False);
				self.return_order_semaphore(sem_id)

	async def send_response_in_landing_page(self, ctx, response : str):
		if response is not None:
			await ctx.send(response, delete_after=10)
		await server.swallow(ctx.message, alert=False);


	async def get_join_semaphore(self, user_id : str):
		sem_id = user_id + '_' + str(random.randrange(10000))
		number_iterations = 0
		while True:
			if self.join_semaphore is None:
				self.join_semaphore = sem_id
				await asyncio.sleep(0.5)
				if self.join_semaphore == sem_id:
					break
			await asyncio.sleep(0.5)
			number_iterations += 1
			if number_iterations > 120:
				print(f'Error: semaphore probably stuck! Resetting semaphore for {sem_id}.')
				self.join_semaphore = None
				return None
		return sem_id

	def return_order_semaphore(self, sem_id : str):
		if self.join_semaphore == sem_id:
			self.join_semaphore = None
		else:
			print(f'Semaphore error for \"player join\": tried to return semaphore for {sem_id} but it was already free!')


	@commands.command(
		name='clear_all_players',
		help='Admin-only. De-initialise all players.',
		hidden=True)
	@commands.has_role('gm')
	async def clear_all_players_command(self, ctx):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		await players.init(ctx.guild, clear_all=True)
		try:
			await ctx.send('Done.')
		except discord.errors.NotFound:
			print('Cleared all players. Could not send report because channel is missing – '
				+'the command was probably given in a player-only command line that was deleted.')

	@commands.command(
		name='clear_all_actors',
		help='Admin-only: de-initialise all actors (players and shops).',
		hidden=True)
	@commands.has_role('gm')
	async def clear_all_actors_command(self, ctx):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		await actors.init(ctx.guild, clear_all=True)
		try:
			await ctx.send('Done.')
		except discord.errors.NotFound:
			print('Cleared all actors. Could not send report because channel is missing – '
				+'the command was probably given in a player-only command line that was deleted.')

	@commands.command(
		name='clear_actor',
		help='Admin-only: de-initialise an actor (player or shop).',
		hidden=True)
	@commands.has_role('gm')
	async def clear_actor_command(self, ctx, actor_id : str):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		report = await actors.clear_actor(ctx.guild, actor_id)
		try:
			await ctx.send(report)
		except discord.errors.NotFound:
			print(f'Cleared actor {actor_id}. Could not send report because channel is missing – '
				+'the command was probably given in a player-only command line that was deleted.')
	
	@commands.command(
		name='ping',
		help='Admin-only. Send a ping to a player\'s cmd_line channel.',
		hidden=True)
	@commands.has_role('gm')
	async def ping_command(self, ctx, player_id : str):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		channel = players.get_cmd_line_channel(player_id)
		if channel is not None:
			await channel.send(f'Testing ping for {player_id}')
		else:
			await ctx.send(f'Error: could not find the command line channel for {player_id}')

	@commands.command(
		name='add_member',
		help='Admin-only. Add a member to a group.',
		hidden=True)
	@commands.has_role('gm')
	async def add_member_command(self, ctx, handle_id : str=None, group_id : str=None):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		report = await groups.add_member_from_handle(ctx.guild, group_id, handle_id)
		if report is not None:
			await ctx.send(report)

	@commands.command(
		name='create_group',
		help='Admin-only. Create a group with yourself as initial member.',
		hidden=True)
	@commands.has_role('gm')
	async def create_group_command(self, ctx, group_name : str=None):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		report = await groups.create_group_from_command(ctx, group_name)
		if report is not None:
			await ctx.send(report)

	@commands.command(
		name='clear_all_groups',
		help='Admin-only. Delete all groups.',
		hidden=True)
	@commands.has_role('gm')
	async def clear_all_groups_command(self, ctx):
		allowed = await channels.pre_process_command(ctx)
		if not allowed:
			return
		await groups.init(ctx.guild, clear_all=True)
		await ctx.send('Done.')



def setup(bot):
	bot.add_cog(AdminCog(bot))