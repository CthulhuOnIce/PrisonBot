import discord
from discord.ext import commands
import yaml
import pickle
import asyncio
from threading import Thread

# https://discord.com/oauth2/authorize?client_id=801880841788719114&scope=bot&permissions=268435472

try:
    with open("config.yml", "r") as r:
        C = yaml.load(r.read(), Loader=yaml.FullLoader)
except FileNotFoundError:
    CRASH("No config.yml, please copy and rename config-example.yml and fill in the appropriate values.")

global_prison_log = {}

bot = commands.Bot(command_prefix=C["prefix"])

def get_list_of_role_ids(user, guild):
	lst = []
	for role in user.roles:
		if role == guild.default_role:	continue
		lst.append(role.id)
	return lst

def authorize(user):
    for role in user.roles:
        if role.id in C["authorizedroles"]:
            return True
    return False

def time_to_seconds(time):
    time_convert = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        return int(time[:-1]) * time_convert[time[-1]]
    except:
        return time

async def prison_man(user, guild, reason=None):
	global_prison_log[str(user.id)] = get_list_of_role_ids(user, guild)
	roles = global_prison_log[str(user.id)]

	for i in roles:
		await user.remove_roles(guild.get_role(i))
	await user.add_roles(guild.get_role(C["muterole"]))

	return

async def unprison_man(user, guild, reason=None):
	if str(user.id) not in global_prison_log:
		return

	roles = global_prison_log[str(user.id)]

	for i in roles:
		await user.add_roles(guild.get_role(i))
	await user.remove_roles(guild.get_role(C["muterole"]))

	global_prison_log.pop(str(user.id))
	return

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=f'{C["prefix"]}prison'))
    print("Ready to go.")

@bot.command()
async def prison(ctx, member:discord.Member, time:str="0", *, reason=None):
    if not authorize(ctx.author):
        await ctx.send("You aren't authorized to do this.")
        return

    if f"{member.id}" in global_prison_log:
    	await ctx.send("Already prisoned this person.")
    	return

    if ctx.author == member:
    	await ctx.send("You can't mute yourself.")
    	return

    if member.top_role >= ctx.author.top_role:
    	await ctx.send("You can only mute people who you outrank.")
    	return

    guild = ctx.guild

    truetime = time_to_seconds(time)

    await prison_man(member, guild, reason=f"Muted by {ctx.author.name} for {truetime} seconds. ({reason})")

    embed = discord.Embed(title="Prisoned!", description=f"{member.mention} has been prisoned. ", colour=discord.Colour.light_gray())
    embed.add_field(name="Moderator: ", value=ctx.author.mention, inline=False)
    embed.add_field(name="Reason:", value=reason, inline=False)
    embed.add_field(name="Time left for the sentence:", value=f"{truetime} seconds.", inline=False)
    await ctx.send(embed=embed)

    if time == "0":  # perma jail
    	return

    await asyncio.sleep(truetime)

    await unprison_man(member, guild, reason="Time expired.")

@bot.command()
async def unprison(ctx, member:discord.Member, *, reason=None):

    if not authorize(ctx.author):
        await ctx.send("You aren't authorized to do this.")
        return

    if not f"{member.id}" in global_prison_log:
        await ctx.send("I didn't mute them, you'll have to do it manually.")
        return

    guild = ctx.guild

    await unprison_man(member, guild, reason=f"Let out early by {ctx.author.name}")

    embed = discord.Embed(title="UnPrisoned!", description=f"{member.mention} has been unprisoned early. ", colour=discord.Colour.light_gray())
    embed.add_field(name="Moderator: ", value=ctx.author.mention, inline=False)
    embed.add_field(name="Reason:", value=reason, inline=False)
    await ctx.send(embed=embed)

bot.run(C["token"])