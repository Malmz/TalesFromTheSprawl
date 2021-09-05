# bot.py
import os
import random
import discord
import asyncio

from configobj import ConfigObj

from discord.ext import commands
from dotenv import load_dotenv

# Custom imports
import handles
import channels
import posting
import reactions
import actors
import players
import finances
import custom_types
import chats
import server
import shops
import groups
import player_setup
import scenarios
import game
import artifacts
from common import coin


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
guild_name = os.getenv('GUILD_NAME')
# Note: for the .table command to work, you must manually set up
# the in-game bar/restaurant as a shop, using .create_shop etc.
main_shop = os.getenv('MAIN_SHOP_NAME')

intents = discord.Intents.default()
intents.members = True

# Change only the no_category default string
help_command = commands.DefaultHelpCommand(
    no_category = 'Commands'
)
bot = commands.Bot(
    command_prefix='.',
    intents=intents,
    help_command = help_command
)

guild = None

# Below cogs represents our folder our cogs are in. Following is the file name. So 'meme.py' in cogs, would be cogs.meme
# Think of it like a dot path import
initial_extensions = ['handles', 'finances']

# Here we load our extensions(cogs) listed above in [initial_extensions].
if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

@bot.event
async def on_ready():
    global guild
    global guild_name
    clear_all = False
    guild = discord.utils.find(lambda g: g.name == guild_name, bot.guilds)
    await server.init(bot, guild)
    await handles.init(clear_all)
    await actors.init(guild, clear_all=clear_all)
    await players.init(guild, clear_all=clear_all)
    await channels.init()
    finances.init_finances()
    await chats.init(clear_all=clear_all)
    await shops.init(guild, clear_all=clear_all)
    await groups.init(guild, clear_all=clear_all)
    artifacts.init(clear_all=clear_all)
    print('Initialization complete.')
    report = game.start_game()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.BadArgument) and 'Converting to "int" failed for parameter "amount"' in str(error):
        await ctx.send("Error: amount must be an integer greater than 0.")
    elif isinstance(error, commands.errors.BadArgument) and 'Converting to "int" failed for parameter "price"' in str(error):
        await ctx.send("Error: price must be an integer greater than 0.")
    elif isinstance(error, commands.errors.CommandNotFound):
        await ctx.send("Error: that is not a known command.")
    else:
        await ctx.send("Error: unknown system error. Contact administrator.")
        raise(error)

async def swallow(message, alert=True):
    await message.delete()
    if alert:
        await message.channel.send(
            'You cannot do that here. Try it in your #cmd_line instead.',
            delete_after=5)


# General message processing (reposting for anonymity/pseudonymity)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        # Never react to bot's own message to avoid loops
        return

    if channels.is_offline_channel(message.channel):
        # No bot shenanigans in the off channel
        return

    if not game.can_process_messages():
        await swallow(message, alert=False)
        return

    if (channels.is_cmd_line(message.channel.name)
        or channels.is_chat_hub(message.channel.name)
        ):
        await bot.process_commands(message)
        return        

    if channels.is_anonymous_channel(message.channel):
        await posting.process_open_message(message, True)
        return

    if channels.is_pseudonymous_channel(message.channel):
        await posting.process_open_message(message)

    if channels.is_chat_channel(message.channel):
        await chats.process_message(message)



# General reaction handling

@bot.event
async def on_raw_reaction_add(payload):
    channel = await bot.fetch_channel(payload.channel_id)
    if payload.user_id == bot.user.id:
        # Don't act on bot's own reactions to avoid loops
        return

    if channels.is_offline_channel(channel):
        # No bot shenanigans in the off channels
        return

    await reactions.process_reaction_add(payload.message_id, payload.user_id, channel, payload.emoji)

# New players

@bot.event
async def on_member_join(member):
    return await players.create_player(member)



# TODO: Fix the .help command:
# - Only show the commands that should be visible to the player
# - Group them by category, not alphabetically





# Admin-only commands for testing etc.

@bot.command(name='fake_join', help='Admin-only function to test run the new member mechanics')
@commands.has_role('gm')
async def fake_join_command(ctx, user_id):
    member_to_fake_join = await ctx.guild.fetch_member(user_id)
    if member_to_fake_join is None:
        await ctx.send(f'Failed: member with user_id {user_id} not found.')
    else:
        report = await on_member_join(member_to_fake_join)
        if report is None:
            report = "Done."
        await ctx.send(report)

@bot.command(name='fake_join_name', help='Admin-only function to test run the new member mechanics')
@commands.has_role('gm')
async def fake_join_command(ctx, name : str):
    members = await ctx.guild.fetch_members(limit=100).flatten()
    member_to_fake_join = discord.utils.find(lambda m: m.name == name, members)
    if member_to_fake_join is None:
        await ctx.send(f'Failed: member with name {name} not found.')
    else:
        report = await on_member_join(member_to_fake_join)
        if report is None:
            report = "Done."
        await ctx.send(report)

@bot.command(name='fake_join_nick', help='Admin-only function to test run the new member mechanics')
@commands.has_role('gm')
async def fake_join_command(ctx, nick : str):
    member_to_fake_join = await server.get_member_from_nick(nick)
    if member_to_fake_join is None:
        await ctx.send(f'Failed: member with nick {nick} not found.')
    else:
        report = await on_member_join(member_to_fake_join)
        if report is None:
            report = "Done."
        await ctx.send(report)

@bot.command(name='clear_all_players', help='Admin-only: de-initialise all players.')
@commands.has_role('gm')
async def clear_all_players_command(ctx):
    await players.init(guild, clear_all=True)
    try:
        await ctx.send('Done.')
    except discord.errors.NotFound:
        print('Cleared all players. Could not send report because channel is missing – '
            +'the command was probably given in a player-only command line that was deleted.')

@bot.command(name='clear_all_actors', help='Admin-only: de-initialise all actors (players and shops).')
@commands.has_role('gm')
async def clear_all_actors_command(ctx):
    await actors.init(guild, clear_all=True)
    try:
        await ctx.send('Done.')
    except discord.errors.NotFound:
        print('Cleared all actors. Could not send report because channel is missing – '
            +'the command was probably given in a player-only command line that was deleted.')

@bot.command(name='clear_actor', help='Admin-only: de-initialise an actor (player or shop).')
@commands.has_role('gm')
async def clear_actor_command(ctx, actor_id : str):
    report = await actors.clear_actor(guild, actor_id)
    try:
        await ctx.send(report)
    except discord.errors.NotFound:
        print(f'Cleared actor {actor_id}. Could not send report because channel is missing – '
            +'the command was probably given in a player-only command line that was deleted.')
    

@bot.command(name='init_all_players', help='Admin-only: initialise all current members of the server as players.')
@commands.has_role('gm')
async def init_all_players_command(ctx):
    await players.initialise_all_users(guild)
    await ctx.send('Done.')

@bot.command(name='ping', help='Admin-only function to test user-player-channel mappings')
@commands.has_role('gm')
async def ping_command(ctx, handle_id : str):
    channel = players.get_cmd_line_channel_for_handle(handle)
    if channel != None:
        await channel.send(f'Testing ping for {handle_id}')
    else:
        await ctx.send(f'Error: could not find the command line channel for {handle_id}')


@bot.command(name='add_known_handle', help='Admin-only function to add a known handle, before the player joins the server.')
@commands.has_role('gm')
async def add_known_handle_command(ctx, handle_id : str):
    if handle_id is None:
        await ctx.send('Error: provide a handle')
    else:
        player_setup.add_known_handle(handle_id)
        await ctx.send(f'Added entry for {handle_id}. Please update its contents manually by editing the file.')




# Chats

# TODO: add handling for using .chat and .close_chat without argument
@bot.command(name='chat', help='Open a chat session with another user.')
async def chat_command(ctx, handle : str):
    handle = handle.lower()
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    await chats.create_chat_from_command(ctx, handle)

@bot.command(name='chat_other', help='Admin-only: open a chat session for someone else.')
async def chat_other_command(ctx,  my_handle : str, other_handle : str):
    my_handle = my_handle.lower()
    other_handle = other_handle.lower()
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await chats.create_2party_chat_from_handle_id(my_handle, other_handle)
    if report != None:
        await ctx.send(report)

@bot.command(name='close_chat', help='Close a chat session from your end.')
async def close_chat_command(ctx, handle : str):
    handle = handle.lower()
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    await chats.close_chat_session_from_command(ctx, handle)


@bot.command(name='close_chat_other', help='Admin-only: close a chat session for someone else.')
@commands.has_role('gm')
async def close_chat_other_command(ctx, my_handle : str, other_handle : str):
    my_handle = my_handle.lower()
    other_handle = other_handle.lower()
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await chats.close_2party_chat_session_from_handle_id(my_handle, other_handle)
    if report is not None:
        await ctx.send(report)

@bot.command(name='clear_all_chats', help='Admin-only: delete all chats and chat channels for all users.')
@commands.has_role('gm')
async def clear_all_chats_command(ctx):
    await chats.init(clear_all=True)
    await ctx.send('Done.')





### shops:

@bot.command(name='create_shop', help='Admin-only: create a new shop, run by a certain player.')
@commands.has_role('gm')
async def create_shop_command(ctx, shop_name : str=None, player_id : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    result = ActionResult = await shops.create_shop(ctx.guild, shop_name, player_id)
    if result.report is not None:
        await ctx.send(result.report)

@bot.command(name='employ', help='Employee only: add a new player to a shop')
async def employ_command(ctx, handle_id : str=None, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await shops.process_employ_command(str(ctx.message.author.id), ctx.guild, handle_id, shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='fire', help='Shop owner only: remove an employee from a shop')
async def employ_command(ctx, handle_id : str=None, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await shops.process_fire_command(str(ctx.message.author.id), handle_id, shop_name)
    if report is not None:
        await ctx.send(report)



@bot.command(name='add_product', help='Employee only: add a new product to a shop.')
async def add_product_command(ctx,
    product_name : str=None,
    description : str=None,
    price : int=0,
    symbol : str=None,
    shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = shops.add_product(str(ctx.message.author.id), product_name, description, price, symbol, shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='edit_product', help='Employee only: edit a product.')
async def edit_product_command(ctx,
    product_name : str=None,
    key : str=None,
    value : str=None,
    shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = shops.edit_product_from_command(str(ctx.message.author.id), product_name, key, value, shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='remove_product', help='Employee only: delete a product from a shop.')
async def remove_product_command(ctx,
    product_name : str=None,
    shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await shops.remove_product(str(ctx.message.author.id), product_name, shop_name)
    if report is not None:
        await ctx.send(report)


@bot.command(name='in_stock', help='Employee only: set a product to be in stock/out of stock.')
async def in_stock_command(ctx,
    product_name : str=None,
    value : bool=True,
    shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await shops.edit_product_from_command(str(ctx.message.author.id), product_name, 'in_stock', str(value), shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='clear_orders', help='Shop owner only: clear a shop\'s orders and update its menu.')
async def clear_orders_command(ctx, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    await shops.reinitialize(str(ctx.message.author.id), shop_name)
    await publish_menu_command(ctx, shop_name=shop_name)


@bot.command(name='publish_menu', help='Employee only: post a shop\'s catalogue/menu.')
async def publish_menu_command(ctx, product_name : str=None, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    if product_name is not None:
        report = await shops.post_catalogue_item(str(ctx.message.author.id), product_name, shop_name)
    else:
        report = await shops.post_catalogue(str(ctx.message.author.id), shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='order', brief='', help='Order a product from a shop.')
async def order_command(ctx, product_name : str=None, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await shops.order_product_from_command(str(ctx.message.author.id), shop_name, product_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='order_other', help='Admin-only: order a product from a shop for someone else.')
@commands.has_role('gm')
async def order_other_command(ctx, product_name : str=None, shop_name : str=None, buyer : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return

    buyer_handle : custom_types.Handle = handles.get_handle(buyer)
    report = await shops.order_product_for_buyer(shop_name, product_name, buyer_handle)
    if report is not None:
        await ctx.send(report)

@bot.command(name='set_delivery_id', help='Set you delivery option at a shop.')
async def set_delivery_id_command(ctx, delivery_id : str=None, shop_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = shops.set_delivery_id_from_command(str(ctx.message.author.id), delivery_id, shop_name)
    if report is not None:
        await ctx.send(report)

@bot.command(name='table', help=f'Tell {main_shop} where to bring your order Valid options are table numbers, \"bar\", and \"call\".')
async def set_delivery_id_command(ctx, option : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = shops.set_delivery_table_from_command(str(ctx.message.author.id), option, main_shop)
    if report is not None:
        await ctx.send(report)



@bot.command(name='clear_all_shops', help='Admin-only: delete all shops.')
@commands.has_role('gm')
async def clear_shops_command(ctx):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    await shops.init(guild, clear_all=True)
    await ctx.send('Done.')






@bot.command(name='create_group', help='Admin-only: create a group, with the current player as initial member')
@commands.has_role('gm')
async def create_group_command(ctx, group_name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await groups.create_group_from_command(ctx, group_name)
    if report is not None:
        await ctx.send(report)


@bot.command(name='clear_all_groups', help='Admin-only: delete all groups.')
@commands.has_role('gm')
async def clear_all_groups_command(ctx):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    await groups.init(guild, clear_all=True)
    await ctx.send('Done.')

@bot.command(name='add_member', help='Admin-only: add a member to a group.')
@commands.has_role('gm')
async def add_member_command(ctx, handle_id : str=None, group_id : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await groups.add_member_from_handle(guild, group_id, handle_id)
    if report is not None:
        await ctx.send(report)



@bot.command(name='run_scenario', help='GM-only: run a scenario.')
@commands.has_role('gm')
async def run_scenario_command(ctx, name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await scenarios.run_scenario(name)
    if report is not None:
        await ctx.send(report)


@bot.command(name='create_scenario', help='GM-only: create a basic scenario.')
@commands.has_role('gm')
async def create_scenario_command(ctx, name : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = await scenarios.create_scenario(name)
    if report is not None:
        await ctx.send(report)



@bot.command(name='create_artifact', help='GM-only: create an artifact.')
@commands.has_role('gm')
async def create_artifact_command(ctx, name : str=None, content : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = artifacts.create_artifact(name, content)
    if report is not None:
        await ctx.send(report)


@bot.command(name='connect', help='Connect to device or remote server.')
async def connect_command(ctx, name : str=None, code : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = artifacts.access_artifact(name, code)
    if report is not None:
        await ctx.send(report)

@bot.command(name='login', help='Connect to device or remote server. Alias: \".connect\"')
async def connect_command(ctx, name : str=None, code : str=None):
    if not channels.is_cmd_line(ctx.channel.name):
        await swallow(ctx.message);
        return
    report = artifacts.access_artifact(name, code)
    if report is not None:
        await ctx.send(report)



bot.run(TOKEN)
