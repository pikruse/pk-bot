# necessary imports
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio

# options
intents = discord.Intents.all()

# music options
FFMPEG_OPTIONS = {"options": "-vn"}
YDL_OPTIONS = {"format": "bestaudio",
               "noplaylist": ""}

# create Music class
class Music(commands.Cog):

    # define init method
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.voice = None
    
    # play next song
    async def play_next(self, interaction: discord.Interaction):
        # if queue exists
        if self.queue:

            # grab url, title from queue
            url, title = self.queue.pop(0)

            # get song info in playable format
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)

            # play song, send message, but only if bot is in vc
            if interaction.guild.voice_client:
                interaction.guild.voice_client.play(source, after=lambda _: self.client.loop.create_task(self.play_next(interaction)))
            else:
                await interaction.channel.send(f"Bot not in voice channel!")
            await interaction.channel.send(f"Now Playing: **{title}**")

        # if queue is empty, disconnect from vc
        elif not interaction.guild.voice_client.is_playing():
            await interaction.guild.voice_client.disconnect()
            await interaction.channel.send(f"Queue is empty. Leaving voice channel.")
        
    # play command
    @app_commands.command(name="play",
                          description="Play audio from a youtube URL")
    @app_commands.describe(search="Song to search for")
    async def play(self, interaction: discord.Interaction,
                   *, search: str):
        
        # check if bot is in a voice channel
        if interaction.guild.voice_client:

            # join same voice channel as user if not in one
            if not interaction.guild.voice_client.channel == interaction.user.voice.channel:
                
                # send message
                await interaction.response.send_message(f"Joining...")

                # get channel
                channel = interaction.user.voice.channel

                # connect
                await channel.connect()

                # change voice attr. to current channel
                self.voice = interaction.guild.voice_client

            # get song info
            async with interaction.channel.typing():

                # use yt-dpl downloader
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(f"ytsearch:{search}", download=False)

                    # if multiple results, get first
                    if "entries" in info:
                        info = info["entries"][0]
                    
                    # get url and title and add to queue
                    url = info["url"]
                    title = info["title"]
                    self.queue.append((url, title))

                    # send message
                    await interaction.response.send_message(f"Added **{title}** to queue!")

            # if bot is not playing, play next song
            if not interaction.guild.voice_client.is_playing():
                await self.play_next(interaction)

        # if bot not in voice channel, send a message
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # join voice channel
    @app_commands.command(name="join",
                          description="Joins a voice channel")
    async def join(self, interaction: discord.Interaction):

        # check if user is in a voice channel
        if interaction.user.voice:

            # send message
            await interaction.response.send_message(f"Joining...")

            # get channel
            channel = interaction.user.voice.channel

            # connect
            await channel.connect()

            # change voice attr. to current channel
            self.voice = interaction.guild.voice_client
        else:
            await interaction.response.send_message(f"You must be in a voice channel to use this command!")


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