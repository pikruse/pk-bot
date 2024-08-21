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

# record latency every 5 seconds
@tasks.loop(seconds=5)
async def record_latency():
    latency_values.append(client.latency * 1000)
    timestamps.append(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%H:%M:%S"))

    # keep only the last 100 values
    if len(latency_values) > 100:
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
    max_ticks = 10  # set max number of ticks on x-axis
    if len(latency_values) < 2:
        await interaction.response.send_message("Not enough data to generate a graph.")
        return
    
    # add regions indicating the status of the latency
    fair = 100
    bad = 200
    x = timestamps
    y_upper = 250 if plt.gca().get_ylim()[1] < 200 else plt.gca().get_ylim()[1]

    x = timestamps
    y = latency_values
    
    fair = 100
    bad = 200
    y_upper = 250 if plt.gca().get_ylim()[1] < 200 else plt.gca().get_ylim()[1]

    plt.figure()
    plt.plot(x, y)
    plt.xlabel("Time")
    plt.ylabel("Latency (ms)")
    plt.title("Bot Latency Over Time")
    plt.xticks(rotation=45)
    
    # reduce number of ticks
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(max_ticks))
    
    plt.tight_layout()
    plt.axhline(y=fair, color='orange')
    plt.axhline(y=bad, color='red')
    
    # adjust for transparency
    plt.fill_between(x, 0, fair, color='green', alpha=0.1, label="Good")
    plt.fill_between(x, fair, bad, color='orange', alpha=0.1, label="Fair")
    plt.fill_between(x, bad, y_upper, color='red', alpha=0.1, label="Bad")
    
    plt.savefig("latency_graph.png")
    plt.close()

    with open("latency_graph.png", "rb") as file:
        await interaction.response.send_message("Here is the graph of the bot's latency", file=discord.File(file))
        return
client.run(TOKEN)