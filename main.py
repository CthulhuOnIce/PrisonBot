import discord
from discord.ext import commands
import yaml
import pickle
import asyncio
from threading import Thread
import time
import datetime
import re
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

try:
	with open("config.yml", "r") as r:
		C = yaml.load(r.read(), Loader=yaml.FullLoader)
except FileNotFoundError:
	print("No config.yml, please copy and rename config-example.yml and fill in the appropriate values.")
	exit()

global_prison_log = {}
prison_ledger = {}
timefinderregex = r"([0-9]+[A-z])"

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

def time_to_seconds(time): # returns either an amount of minutes, or -1 to signify it's not a time at all, rather a part of the prison reason
	matches = re.findall(timefinderregex, time)
	time_convert = {"s": 1, "m": 60, "h": 3600, "d": 86400}
	if not len(matches):
		try:
			return int(time)
		except:
			return -1
	finaltime = 0
	for match in matches:
		finaltime += int(match[:-1]) * time_convert[match[-1]]
	return finaltime

def time_to_text(length): # TODO: atm it only allows one number and one unit, ie "5h", allow it to split and do multiple units, ie "1h30m"
	days = round(length // (24 * 3600))
	length = length % (24 * 3600)
	hours = round(length // 3600)
	length %= 3600
	minutes = round(length // 60)
	length %= 60
	seconds = round(length)
	txt = ""
	if seconds:  txt = f"{seconds} second{'s' if seconds != 1  else ''}"
	if minutes:   txt = f"{minutes} minute{'s' if minutes != 1 else ''}, " + txt
	if hours:     txt = f"{hours} hour{'s' if hours != 1 else ''}, " + txt
	if days:      txt = f"{days} day{'s' if days != 1 else ''}, " + txt
	return txt.strip(", ")
		
async def prison_man(user, guild, ledger, summary=None):
	global_prison_log[str(user.id)] = get_list_of_role_ids(user, guild)
	prison_ledger[str(user.id)] = ledger
	roles = global_prison_log[str(user.id)]

	for i in roles:
		await user.remove_roles(guild.get_role(i), reason=summary)
	await user.add_roles(guild.get_role(C["muterole"]), reason=summary)

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
async def prison(ctx, member:discord.Member, jailtime:str="0", *, reason=None):
	if not authorize(ctx.author):
		await ctx.send("You aren't authorized to do this.")
		return

	if ctx.author == member:
		await ctx.send("You can't prison yourself.")
		return

	if member.top_role >= ctx.author.top_role:
		await ctx.send("You can only prison people who you outrank.")
		return

	if f"{member.id}" in global_prison_log:
		await ctx.send("Already prisoned this person.")
		return

	guild = ctx.guild

	truetime = time_to_seconds(jailtime)

	if truetime < 0: # hotfix
		reason = f"{jailtime} {reason if reason else ''}"
		truetime = 0
		jailtime = "0"

	await prison_man(member, guild, {"time_jailed": time.time(), "sentence": truetime, "reason": reason, "admin": ctx.author, "member": member}, summary=f"Muted by {ctx.author.name} for {time_to_text(truetime)}. ({reason})")

	embed = discord.Embed(title="Prisoned!", description=f"{member.mention} has been prisoned. ", colour=discord.Colour.light_gray())
	embed.add_field(name="Moderator: ", value=ctx.author.mention, inline=False)
	embed.add_field(name="Reason: ", value=reason, inline=False)
	embed.add_field(name="Time left for the sentence: ", value=time_to_text(truetime) if truetime != 0 else "Until released.", inline=False)
	embed.add_field(name="Extra Info: ", value=f"Use {C['prefix']}sentence to see how much time you or someone else has left")

	try:
		await member.send(embed=embed)
	except:
		embed.set_footer(text="I couldn't DM them.")

	await ctx.send(embed=embed)

	if jailtime == "0":  # perma jail
		return

	await asyncio.sleep(truetime)

	try:
		embed = discord.Embed(title="Unprisoned", description=f"{member.mention} has been unprisoned. ", colour=discord.Colour.light_gray())
		embed.add_field(name="Reason: ", value="Your prison sentence has expired.", inline=False)
		await member.send(embed=embed)
	except:
		pass

	await unprison_man(member, guild, reason="Time expired.")

@bot.command(brief="Admins only: Unprison a user.")
async def unprison(ctx, member:discord.Member, *, reason=None):

	if not authorize(ctx.author):
		await ctx.send("You aren't authorized to do this.")
		return

	if not f"{member.id}" in global_prison_log:
		await ctx.send("I didn't prison them, you'll have to do it manually.")
		return

	guild = ctx.guild

	await unprison_man(member, guild, reason=f"Let out early by {ctx.author.name}")

	embed = discord.Embed(title="UnPrisoned!", description=f"{member.mention} has been unprisoned early. ", colour=discord.Colour.light_gray())
	embed.add_field(name="Moderator: ", value=ctx.author.mention, inline=False)
	embed.add_field(name="Reason:", value=reason, inline=False)

	try:
		await member.send(embed=embed)
	except:
		embed.set_footer(text="I couldn't DM them.")

	await ctx.send(embed=embed)

@bot.command(brief="Get time left in sentence.")
async def sentence(ctx, member:discord.Member=None):
	if not member:		member = ctx.author
	if str(member.id) not in prison_ledger:
		await ctx.send(f"The bot wasn't used to prison {member.mention}, you'll have to ask the mod who did it manually.")
		return
	sentence_log = prison_ledger[str(member.id)]
	timeremainingsec = sentence_log["time_jailed"] + sentence_log["sentence"] - time.time()
	embed = discord.Embed(title=f"Prison Info", description=f"{member.mention}'s Prison Info", colour=discord.Colour.light_gray())
	embed.add_field(name="Moderator: ", value=sentence_log["admin"].mention, inline=False)
	embed.add_field(name="Reason: ", value=sentence_log["reason"] if sentence_log["reason"] else "None given.", inline=False)
	embed.add_field(name="Sentence: ", value=time_to_text(sentence_log["sentence"]) if sentence_log["sentence"] else "Indefinitely", inline=False)
	embed.add_field(name="Time Left:", value=time_to_text(timeremainingsec) if sentence_log["sentence"] else "Indefinitely", inline=False)
	await ctx.send(embed=embed)

@bot.command(brief="Get list of currently imprisoned members.")
async def prisoners(ctx):
	pages = []
	for prisoner_id in prison_ledger:
		prisoner = prison_ledger[prisoner_id]
		timeremainingsec = prisoner["time_jailed"] + prisoner["sentence"] - time.time()
		embed = discord.Embed(title=f"Current Prisoners", description=prisoner["member"].mention, colour=discord.Colour.light_gray())
		embed.add_field(name="Moderator: ", value=prisoner["admin"].mention, inline=False)
		embed.add_field(name="Reason: ", value=prisoner["reason"] if prisoner["reason"] else "None given.", inline=False)
		embed.add_field(name="Sentence: ", value=time_to_text(prisoner["sentence"]) if prisoner["sentence"] else "Indefinitely", inline=False)
		embed.add_field(name="Time Left:", value=time_to_text(timeremainingsec) if prisoner["sentence"] else "Indefinitely", inline=False)
		pages.append(embed)
	if len(pages):
		paginator = BotEmbedPaginator(ctx, pages)
		await paginator.run()
	else:
		await ctx.send("I'm currently not tracking any prisoners.\nEither there are no prisoners, or they were all placed there manually.")

@bot.command(brief="Admin Only: Verify a user.")
async def verify(ctx, member:discord.Member):
	if not authorize(ctx.author):
		await ctx.send("You aren't authorized to do this.")
		return
	for i in member.roles:
		if "unverified" in i.name.lower():
			await member.remove_roles(i)
	await member.add_roles(ctx.guild.get_role(C["verifiedrole"]))
	await ctx.message.add_reaction("✔")

bot.run(C["token"])
