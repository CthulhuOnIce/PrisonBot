import discord
from discord.ext import commands
import yaml
import pickle
import asyncio
from threading import Thread
import time
import datetime

# https://discord.com/oauth2/authorize?client_id=801880841788719114&scope=bot&permissions=268435472

try:
	with open("config.yml", "r") as r:
		C = yaml.load(r.read(), Loader=yaml.FullLoader)
except FileNotFoundError:
	CRASH("No config.yml, please copy and rename config-example.yml and fill in the appropriate values.")

global_prison_log = {}
prison_ledger = {}

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
		try:
			return int(time)
		except:
			return -1

async def prison_man(user, guild, truetime, reason=None):
	global_prison_log[str(user.id)] = get_list_of_role_ids(user, guild)
	prison_ledger[str(user.id)] = {"time_jailed": time.time(), "sentence": truetime, "reason": reason}
	roles = global_prison_log[str(user.id)]

	for i in roles:
		await user.remove_roles(guild.get_role(i), reason=reason)
	await user.add_roles(guild.get_role(C["muterole"]), reason=reason)

	return

async def unprison_man(user, guild, reason=None):
	if str(user.id) not in global_prison_log:
		return

	roles = global_prison_log[str(user.id)]

	for i in roles:
		await user.add_roles(guild.get_role(i), reason=reason)
	await user.remove_roles(guild.get_role(C["muterole"]), reason=reason)

	global_prison_log.pop(str(user.id))
	prison_ledger.pop(str(user.id))
	return

@bot.event
async def on_ready():
	await bot.change_presence(activity=discord.Game(name=f'{C["prefix"]}prison'))
	print("Ready to go.")

@bot.command(brief="Admins only: Prison a user.")
async def prison(ctx, member:discord.Member, time:str="0", *, reason=None):
	if not authorize(ctx.author):
		await ctx.send("You aren't authorized to do this.")
		return

	if ctx.author == member:
		await ctx.send("You can't prison yourself.")
		return

	if member.top_role >= ctx.author.top_role:
		await ctx.send("You can only mute people who you outrank.")
		return

	if f"{member.id}" in global_prison_log:
		await ctx.send("Already prisoned this person.")
		return

	guild = ctx.guild

	truetime = time_to_seconds(time)

	if truetime < 0: # hotfix
		reason = time
		truetime = 0
		time = "0"

	await prison_man(member, guild, truetime, reason=f"Muted by {ctx.author.name} for {truetime} seconds. ({reason})")

	embed = discord.Embed(title="Prisoned!", description=f"{member.mention} has been prisoned. ", colour=discord.Colour.light_gray())
	embed.add_field(name="Moderator: ", value=ctx.author.mention, inline=False)
	embed.add_field(name="Reason:", value=reason, inline=False)
	embed.add_field(name="Time left for the sentence:", value=f"{truetime} seconds." if time != "0" else "Until released.", inline=False)
	await ctx.send(embed=embed)

	if time == "0":  # perma jail
		return

	await asyncio.sleep(truetime)

	await unprison_man(member, guild, reason="Time expired.")

@bot.command(brief="Admins only: Unprison a user.")
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

@bot.command(brief="Get time left in sentence.")
async def sentence(ctx, member:discord.Member=None):
	if not member:		member = ctx.author
	if str(member.id) not in prison_ledger:
		await ctx.send(f"I didn't prison {member.mention}, ask the mod who did.")
	sentence_log = prison_ledger[str(member.id)]
	if sentence_log["sentence"] <= 0:
		embed = discord.Embed(title=f"Prison Info", description=f"{member.mention}'s Prison Info", colour=discord.Colour.light_gray())
		embed.add_field(name="Reason: ", value=sentence_log["reason"])
		embed.add_field(name="Time Left:", value=f"Indefinitely", inline=False)
		await ctx.send(embed=embed)
		return
	timeremainingsec = sentence_log["time_jailed"] + sentence_log["sentence"] - time.time()
	day = round(timeremainingsec // (24 * 3600))
	timeremainingsec = timeremainingsec % (24 * 3600)
	hour = round(timeremainingsec // 3600)
	timeremainingsec %= 3600
	minutes = round(timeremainingsec // 60)
	timeremainingsec %= 60
	seconds = round(timeremainingsec)
	embed = discord.Embed(title=f"Prison Info", description=f"{member.mention}'s Prison Info", colour=discord.Colour.light_gray())
	embed.add_field(name="Reason: ", value=sentence_log["reason"])
	embed.add_field(name="Time Left:", value=f"{day} days, {hour} hours, {minutes} minutes, and {seconds} seconds", inline=False)
	await ctx.send(embed=embed)


bot.run(C["token"])