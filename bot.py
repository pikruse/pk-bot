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

#####################
### INITIAL SETUP ###
#####################

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

##############
### EVENTS ###
##############

# on_ready event is triggered when the bot is ready to work
@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD))
    # print "ready" in the console when the bot is ready to work
    print("ready")
    record_latency.start()

# implement reaction role 
@client.event
async def on_raw_reaction_add(payload):
    if not payload.guild_id:
        return
    guild = client.get_guild(payload.guild_id) # Get guild
    member = discord.utils.get(guild.members, id=payload.user_id) # Get the member out of the guild
    # The channel ID should be an integer:
    if payload.channel_id == 1276158966497411123: # Only channel where it will work
        if str(payload.emoji) == "🎙️": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1276172227326246944) # Role ID
        elif str(payload.emoji) == "🧑‍🔬": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1276172284134162634)
        elif str(payload.emoji) == "💻": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1276172316492959897)
        else:
            role = discord.utils.get(guild.roles, name=payload.emoji)
        if role is not None: # If role exists
            await payload.member.add_roles(role)
            print(f"Added {role}")

@client.event
async def on_raw_reaction_remove(payload):
    if not payload.guild_id:
        return
    guild = client.get_guild(payload.guild_id)
    member = discord.utils.get(guild.members, id=payload.user_id)
    if payload.channel_id == 1276158966497411123: # Only channel where it will work
        if str(payload.emoji) == "🎙️": # Your emoji
            role = discord.utils.get(guild.roles, id=1276172227326246944) # Role ID
        elif str(payload.emoji) == "🧑‍🔬": # Your emoji
            role = discord.utils.get(guild.roles, id=1276172284134162634)
        elif str(payload.emoji) == "💻": # Your emoji
            role = discord.utils.get(guild.roles, id=1276172316492959897)
        else:
            role = discord.utils.get(guild.roles, name=payload.emoji)
        if role is not None: # If role exists
            await member.remove_roles(role)
            print(f"Removed {role}")


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

################
### COMMANDS ###
################

# add a simple hello command
@tree.command(
    name="hello",
    description="Say Hello!",
    guild=discord.Object(id=GUILD))
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")

# add a command to display the bot's latency in a graph
@tree.command(name="ping", 
              description="Displays the bot's latency in graph or text format",
              guild=discord.Object(id=GUILD))
async def ping(interaction: discord.Interaction,
                        format: str = "text"):
    if format == "text":
            latency = client.latency * 1000
            if latency < 100:
                status = "Good! 🟢"
            elif latency < 200:
                status = "Fair! 🟠"
            else:
                status = "Bad! 🔴"
            await interaction.response.send_message(f"Your latency is {latency:.2f}. {status}")
    else:
        max_ticks = 10  # set max number of ticks on x-axis
        if len(latency_values) < 2:
            await interaction.response.send_message("Not enough data to generate a graph.")
            return
        
        fair = 100
        bad = 200

        x = timestamps
        y = latency_values

        y_upper = max(250, plt.gca().get_ylim()[1])
        
        plt.figure()
        plt.plot(x, y)
        plt.xlabel("Time")
        plt.ylabel("Latency (ms)")
        plt.title("Bot Latency Over Time")
        plt.xticks(rotation=45)
        
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(max_ticks))

        plt.xlim(min(x), max(x))
        plt.ylim(0, y_upper)
        
        plt.axhline(y=fair, color='orange')
        plt.axhline(y=bad, color='red')
        
        plt.fill_between(x, 0, fair, color='green', alpha=0.1, label="Good")
        plt.fill_between(x, fair, bad, color='orange', alpha=0.1, label="Fair")
        plt.fill_between(x, bad, y_upper, color='red', alpha=0.1, label="Bad")
        
        plt.savefig("latency_graph.png", bbox_inches='tight')
        plt.close()

        with open("latency_graph.png", "rb") as file:
            await interaction.response.send_message("Here is the graph of the bot's latency", file=discord.File(file))
            return

# display the pfp of the user
@tree.command(
    name="pfp",
    description="Displays user's pfp",
    guild=discord.Object(id=GUILD)
)
async def pfp(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        await interaction.response.send_message("Error: Please mention a user.")
        return

    user_avatar_url = member.display_avatar.url
    await interaction.response.send_message(f"** @{member.name} pfp:** {user_avatar_url}")

# This sends or updates an embed message with a description of the roles.
@tree.command(name="embed",
              description="Send an embed message with roles",
              guild=discord.Object(id=GUILD))
async def embed(ctx: commands.Context):
    channel = client.get_channel(1276158966497411123)
    emb = discord.Embed(title="React to this message to get your roles!",
                        description="Click the corresponding emoji to receive your role.\n🎙️"
                                    " - Artist\n🧑‍🔬"
                                    " - Producer\n💻"
                                    " - Developer",
                                    color=discord.Color.pink())
    emb.set_thumbnail(url=ctx.guild.icon.url)
    msg = await channel.send(embed=emb)
    await msg.add_reaction("🧑‍🔬")
    await msg.add_reaction("💻")
    await msg.add_reaction("🎙️")

# add a "command not found" message
@client.event
async def on_command_error(ctx, error):
    if ctx.message.content.count('/') <= 1:
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("This command does not exist! Contact the bot devs for more information.")
        else:
            await ctx.send(error)

client.run(TOKEN)