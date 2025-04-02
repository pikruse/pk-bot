# necessary imports
import discord
from discord import app_commands
from discord import PCMVolumeTransformer
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio

# options
intents = discord.Intents.all()

# music options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.3"'
}

YDL_OPTIONS = {"format": "bestaudio",
               "noplaylist": "",
               "cookies": "cookies.txt"}

# create Music class
class Music(commands.Cog):

    # define init method
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.voice = None
        self.current_source = None
    
    # play next song
    async def play_next(self, interaction: discord.Interaction):
        if self.queue:
            url, title = self.queue.pop(0)
            
            # Create PCM audio source
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            
            if interaction.guild.voice_client:
                interaction.guild.voice_client.play(
                    source,
                    after=lambda _: self.client.loop.create_task(self.play_next(interaction))
                )
            await interaction.channel.send(f"Now Playing: **{title}**")
        elif interaction.guild.voice_client and not interaction.guild.voice_client.is_playing():
            await interaction.guild.voice_client.disconnect()
            await interaction.channel.send("Queue empty. Leaving voice channel.")

    # play command
    @app_commands.command(name="play",
                          description="Play audio from a youtube URL")
    @app_commands.describe(search="Song to search for")
    async def play(self, interaction: discord.Interaction, *, search: str):
        await interaction.response.defer()  # Defer FIRST THING
        
        # make sure user is in vc
        if not interaction.user.voice:
            return await interaction.followup.send("You need to be in a voice channel to play music!")
        # get vc
        voice_client = interaction.guild.voice_client

        try:
            if not voice_client:
                # Join channel if not connected
                channel = interaction.user.voice.channel
                voice_client = await channel.connect(timeout=10.0)
                self.voice = voice_client
            elif voice_client.channel != interaction.user.voice.channel:
                # Move to new channel if in different one
                await voice_client.move_to(interaction.user.voice.channel)
        except Exception as e:
            return await interaction.followup.send(f"Failed to join voice channel: {str(e)}")

        # Now process the song
        async with interaction.channel.typing():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)
                
                if "entries" in info:
                    info = info["entries"][0]
                    
                url = info["url"]
                title = info["title"]
                self.queue.append((url, title))

        await interaction.followup.send(f"Added **{title}** to queue!")

        # Start playing if not already
        if not voice_client.is_playing():
            await self.play_next(interaction)

    # join voice channel
    @app_commands.command(name="join",
                          description="Joins a voice channel")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer immediately
        
        if interaction.user.voice:
            try:
                channel = interaction.user.voice.channel
                await channel.connect(timeout=10.0)  # Increased timeout
                self.voice = interaction.guild.voice_client
                await interaction.followup.send(f"Joined {channel.name}!")
            except asyncio.TimeoutError:
                await interaction.followup.send("Connection timed out. Please try again.")
            except Exception as e:
                await interaction.followup.send(f"Failed to join: {str(e)}")
        else:
            await interaction.followup.send("You must be in a voice channel!")
    
    # view queue command
    @app_commands.command(name="queue",
                          description="Shows current queue")
    async def queue(self, interaction: discord.Interaction):
        # if bot not in vc, send message
        if not interaction.guild.voice_client:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

        # if bot in vc
        else:
            # if queue is empty, send message
            if len(self.queue) == 0:
                queue_str = "No songs in queue!"
            
            # if queue is not empty, join song titles with newlines
            else:
                queue_str = "\n".join([f"*{i}*: **{info[1]}**" for i, info in enumerate(self.queue)])

            # create embed and send message
            emb = discord.Embed(title="**Next Up**",
                                color=discord.Color.purple(),
                                description=queue_str)
            await interaction.response.send_message(embed=emb)

    # clear queue command
    @app_commands.command(name="clear_queue",
                          description="Clears the current queue")
    async def clear_queue(self, interaction: discord.Interaction):

        # if queue exists
        if len(self.queue) > 0:

            # clear and message
            self.queue.clear()
            await interaction.response.send_message("Queue cleared!")
        
        # if queue does not exist, send message
        else:
            await interaction.response.send_message("There is no queue to clear!")

    # skip command
    @app_commands.command(name="skip",
                  description="Skips the current audio")
    async def skip(self, interaction: discord.Interaction):

        # if bot in vc
        if interaction.guild.voice_client:

            # if queue is empty, send message
            if len(self.queue) == 0:
                await interaction.response.send_message(f"No songs in queue!")
            
            # if queue is not empty
            else:

                # remove first item from queue and skip
                self.queue.pop(0)

                # activate the next song in queue
                # play_next(self.queue, interaction.guild.voice_client)

                # send message
                await interaction.response.send_message(f"Skipped!")
        
        # if bot not in vc
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # pause command
    @app_commands.command(name="pause",
                description="Pauses audio")
    async def pause(self, interaction: discord.Interaction):
        
        # if bot is in vc
        if interaction.guild.voice_client:

            # if audio is already paused
            if interaction.guild.voice_client.is_paused():

                # send message and return
                await interaction.response.send_message(f"Audio is already paused!")
                return

            # if audio is not paused, pause and send message
            interaction.guild.voice_client.pause()
            await interaction.response.send_message(f"Audio paused!")
        
        # if bot not in vc, send message
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # resume command
    @app_commands.command(name = "resume",
                          description = "Resumes audio")
    async def resume(self, interaction: discord.Interaction):

        # if bot is in vc
        if interaction.guild.voice_client:

            # if bot is already paused
            if interaction.guild.voice_client.is_paused():
                
                # resume and send message
                await interaction.response.send_message(f"Resuming audio...")
                interaction.guild.voice_client.resume()
            
            # if not already paused, send message
            else:
                await interaction.response.send_message(f"Audio is not currently paused!")
        
        # if bot not in vc
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # stop command
    @app_commands.command(name = "stop",
                          description = "Stops audio")
    async def stop(self, interaction: discord.Interaction):

        # if bot is in vc
        if interaction.guild.voice_client:

            # disconnect from voice channel and send message
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message(f"Stopped audio!")
        
        # if bot not in vc
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")
    
# create setup function for cog
async def setup(bot):
    await bot.add_cog(Music(bot))