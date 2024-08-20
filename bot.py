import discord
import os
import datetime
import asyncio

from dotenv import load_dotenv
from discord import app_commands
from discord.ext import tasks, commands

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

intents = discord.Intents.all()

client = commands.Bot(command_prefix='/', intents=intents)
tree = client.tree

# on_ready event is triggered when the bot is ready to work
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD))
    # print "ready" in the console when the bot is ready to work
    print("ready")

# on_member_join event is triggered when a new member joins the server
@client.event
async def on_member_join(member):
    guild = member.guild
    channel = guild.system_channel #system channel (welcome channel)
    if channel:
        await channel.send(f"Thank You for joining {guild}, {member.mention}!")

# on_member_remove event is triggered when a member leaves the server
@client.event
async def on_member_remove(member):
    guild = member.guild
    channel = guild.system_channel
    if channel:
        await channel.send(f"Goodbye {member.mention}!")

# add a simple hello command
@tree.command(
    name="hello",
    description="Say Hello!",
    guild=discord.Object(id=GUILD))
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")

# add a simple ping command
@tree.command(
    name="ping",
    description="Displays the bot's latency in milliseconds",
    guild=discord.Object(id=GUILD))
async def ping(interaction: discord.Interaction):
    latency = client.latency * 1000
    if latency < 100:
        status = f"Your latency is {latency}. That's good! 🟢"
    elif latency < 200:
        status = f"Your latency is {latency}. kill yourself! 🟠"
    else:
        status = f"Your latency is {latency}. That's ass!"
    

client.run(TOKEN)