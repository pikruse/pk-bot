import discord
import os
import datetime
import asyncio
import matplotlib.pyplot as plt
import numpy as np
import time
import yt_dlp

from dotenv import load_dotenv
from discord import app_commands
from discord.ext import tasks, commands

# custom imports
from cogs.music import YTDLSource

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

# music options
# Setup Youtube DL library
ytdl_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

# setup FFmpeg
ffmpeg_options = {
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_options)

# discord opus
discord.opus.load_opus('libopus.dylib')
if not discord.opus.is_loaded():
    raise RuntimeError('Opus failed to load')

# record latency every 5 seconds
@tasks.loop(seconds=5)
async def record_latency():
    latency_values.append(client.latency * 1000)
    timestamps.append(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%H:%M:%S"))

    # keep only the last 100 values
    if len(latency_values) > 100:
        latency_values.pop(0)
        timestamps.pop(0)

async def load_cogs():
    # load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await client.load_extension(f'cogs.{filename[:-3]}')
                print(f'{filename} cog loaded.')
            except Exception as e:
                print(f'Failed to load {filename} cog: {e}')

##############
### EVENTS ###
##############

# on_ready event is triggered when the bot is ready to work
@client.event
async def on_ready():
    # sync
    await tree.sync(guild = discord.Object(id=GUILD))
    print(f'Command tree synced with guild {GUILD}.')

    # print "ready" in the console when the bot is ready to work
    print("ready")

    # start recording latency
    record_latency.start()

# implement reaction role 
@client.event
async def on_raw_reaction_add(payload):
    if not payload.guild_id:
        return
    guild = client.get_guild(payload.guild_id) # Get guild
    member = discord.utils.get(guild.members, id=payload.user_id) # Get the member out of the guild
    # The channel ID should be an integer:
    if payload.channel_id == 1276157069095080067: # Only channel where it will work
        if str(payload.emoji) == "🎙️": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1275822380761219124) # Role ID
        elif str(payload.emoji) == "🧑‍🔬": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1275822336704123021)
        elif str(payload.emoji) == "💻": # Your emoji
            role = discord.utils.get(payload.member.guild.roles, id=1275822444946526208)
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
    if payload.channel_id == 1276157069095080067: # Only channel where it will work
        if str(payload.emoji) == "🎙️": # Your emoji
            role = discord.utils.get(guild.roles, id=1275822380761219124) # Role ID
        elif str(payload.emoji) == "🧑‍🔬": # Your emoji
            role = discord.utils.get(guild.roles, id=1275822336704123021)
        elif str(payload.emoji) == "💻": # Your emoji
            role = discord.utils.get(guild.roles, id=1275822444946526208)
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
        await channel.send(f"Thank You for joining **{guild}**, {member.mention}!")

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
    description="Say Hello!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")

@tree.command(
    name="kick",
    description="Kicks a user (admin only)"
)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permissions! Contact an administrator..", ephemeral=True)
        return
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member.mention} has been kicked for: {reason}")

@tree.command(
    name="timeout",
    description="Times out a user (admin only)"
)
async def timeout(interaction: discord.Interaction, 
                  member: discord.Member, 
                  duration: int, 
                  reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permissions! Contact an administrator...", ephemeral=True)
        return
    await member.timeout(datetime.timedelta(minutes=duration), reason=reason)
    await interaction.response.send_message(f"{member.mention} has been timed out for {duration} seconds for: {reason}")

# add a command to display the bot's latency in a graph
@tree.command(name="ping", 
              description="Displays the bot's latency in graph or text format")
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
    description="Displays user's pfp")
async def pfp(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        await interaction.response.send_message("Error: Please mention a user.")
        return

    user_avatar_url = member.display_avatar.url
    await interaction.response.send_message(f"** @{member.name} pfp:** {user_avatar_url}")

@tree.command(name='credits', description='Returns the bot credits')
async def credits(interaction: discord.Interaction):
    emb = discord.Embed(title="Credits",
                        description="This bot was created by @prod_pk, @obkruse, and @kamel",
                        color=discord.Color.purple())
    await interaction.response.send_message(embed=emb)

# This sends or updates an embed message with a description of the roles.
@tree.command(name="embed",
              description="Send an embed message with roles")
async def embed(ctx: commands.Context):
    channel = client.get_channel(1276157069095080067)
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

# join voice channel
@tree.command(name="join",
                     description="Joins a voice channel",)
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.response.send_message(f"Joining...")
        channel = interaction.user.voice.channel
        await channel.connect()
    else:
        await interaction.response.send_message(f"You must be in a voice channel to use this command!")

# play command
@tree.command(name="play",
              description="Play audio from a youtube URL",)
@app_commands.describe(url="URL of the video to play")
async def play(interaction: discord.Interaction,
               url: str):
    await interaction.response.send_message(f"Attempting to play **{url}**")
    player = await YTDLSource.from_url(url, stream=True)
    guild = interaction.guild
    guild.voice_client.play(player, after=lambda e: print(f'Player error **{e}**') if e else None)


# queue command
@tree.command(name="queue",
                description="Queues a song to play")
async def queue(interaction: discord.Interaction, url: str):
    if interaction.guild.voice_client:
        player = await YTDLSource.from_url(url, stream=True)
        interaction.guild.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        await interaction.response.send_message(f"Queued {player.title}!")
    else:
        await interaction.response.send_message(f"Not currently in a voice channel!")

# view queue command
@tree.command(name="view_queue",
              description="Shows current queue")
async def view_queue(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        await interaction.response.send_message(f"Not currently in a voice channel!")
    else:
        if not interaction.guild.voice_client:
            queue_str = "No songs in queue!"
        else:
            queue_str = "\n".join([f"*{i}*. **{song.title}**" for i, song in enumerate(interaction.guild.voice_client.queue)])
    emb = discord.Embed(title="**Current Queue**",
                        color=discord.Color.purple(),
                        description=queue_str)
    await interaction.response.send_message(embed=emb)

# skip command
@tree.command(name="skip",
              description="Skips the current audio")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.skip()
        await interaction.response.send_message(f"Skipped!")
    else:
        await interaction.response.send_message(f"Not currently in a voice channel!")


# pause command
@tree.command(name="pause",
              description="Pauses audio")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        if interaction.guild.voice_client.is_paused():
            await interaction.response.send_message(f"Audio is already paused!")
            return
        interaction.guild.voice_client.pause()
        await interaction.response.send_message(f"Audio paused!")
    else:
        await interaction.response.send_message(f"Not currently in a voice channel!")

# resume command
@tree.command(name = "resume",
              description = "Resumes audio")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        if interaction.guild.voice_client.is_paused():
            await interaction.response.send_message(f"Resuming audio...")
            interaction.guild.voice_client.resume()
        else:
            await interaction.response.send_message(f"Audio is not currently paused!")
    else:
        await interaction.response.send_message(f"Not currently in a voice channel!")

# stop command
@tree.command(name = "stop",
              description = "Stops audio",
              guild = discord.Object(id=GUILD))
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message(f"Stopped audio!")
    else:
        await interaction.response.send_message(f"Not currently in a voice channel!")
        
# add a "command not found" message
@client.event
async def on_command_error(ctx, error):
    if ctx.message.content.count('/') <= 1:
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("This command does not exist! Contact the bot devs for more information.")
        else:
            await ctx.send(error)

client.run(TOKEN)