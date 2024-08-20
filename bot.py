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
intents.messages = True

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_member_join(member):
    guild = member.guild
    channel = guild.system_channel #system channel (welcome channel)
    if channel:
        await channel.send(f"Thank You for joining {member.mention}!")


client.run(TOKEN)