import discord
import os
import datetime
import asyncio
import matplotlib.pyplot as plt
import numpy as np
import time

from dotenv import load_dotenv
from discord import app_commands
from discord.ext import tasks, commands

load_dotenv()

# get token and guild from the .env file
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

# get intents instance
intents = discord.Intents.all()
client = commands.Bot(command_prefix='/', intents=intents)
tree = client.tree
latency_values = []
timestamps = []

# record latency every 20 seconds
@tasks.loop(seconds=20)
async def record_latency():
    latency_values.append(client.latency * 1000)  # Convert to ms
    timestamps.append(time.time())  # Store current timestamp

    # Keep only the last 10 values for example
    if len(latency_values) > 10:
        latency_values.pop(0)
        timestamps.pop(0)

# on_ready event is triggered when the bot is ready to work
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD))
    # print "ready" in the console when the bot is ready to work
    print("ready")
    record_latency.start()

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

# add a simple ping command to display current latency
@tree.command(
    name="ping",
    description="Displays the bot's latency in milliseconds",
    guild=discord.Object(id=GUILD))
async def ping(interaction: discord.Interaction):
    latency = client.latency * 1000
    if latency < 100:
        status = "Good! 🟢"
    elif latency < 200:
        status = "Fair! 🟠"
    else:
        status = "Bad! 🔴"
    await interaction.response.send_message(f"Your latency is {latency:.2f}. {status}")

# graph the most recent latency values
@tree.command(name="graph_latency", 
              description="Displays the bot's latency in a graph",
              guild=discord.Object(id=GUILD))
async def graph_latency(interaction: discord.Interaction):
    # Ensure there are enough data points
    if len(latency_values) < 2:
        await interaction.response.send_message("Not enough data to generate a graph.")

    # Generate graph
    plt.figure()
    plt.plot(timestamps, latency_values, marker='o')
    plt.xlabel("Time")
    plt.ylabel("Latency (ms)")
    plt.title("Bot Latency Over Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("latency_graph.png")
    plt.close()

    with open("latency_graph.png", "rb") as file:
        await interaction.response.send_message("Here is the graph of the bot's latency", file=discord.File(file))


client.run(TOKEN)