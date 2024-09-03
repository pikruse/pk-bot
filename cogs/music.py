# necessary imports
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio

# options
load_dotenv()

intents = discord.Intents.all()

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

# create YTDLSource class
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self,
                 source,
                 *,
                 data,
                 volume=0.5):
        
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
    
    # define method to get the source from a URL
    @classmethod
    async def from_url(cls,
                       url, 
                       *, 
                       loop=None, 
                       stream=False):
        
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


# create Music class
class Music(commands.Cog):

    # define init method
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.voice = None
    
    # define play_next method
    def play_next(self):
        if len(self.queue) == 0:
            return
        player = YTDLSource.from_url(self.queue[0], loop=self.client.loop)
        self.voice.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
    
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

    # play command
    @app_commands.command(name="play",
                          description="Play audio from a youtube URL")
    @app_commands.describe(url="URL of the video to play")
    async def play(self, interaction: discord.Interaction,
                   url: str):
        
        # check if bot is in a voice channel
        if interaction.guild.voice_client:

            # check length of queue
            if len(self.queue) == 0:
                await interaction.response.send_message(f"Playing audio...")
                self.queue.append(url)
                player = await YTDLSource.from_url(url, loop=self.client.loop)
                interaction.guild.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        # if bot not in voice channel, send a message
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # view queue command
    @app_commands.command(name="view_queue",
                          description="Shows current queue")
    async def view_queue(self, interaction: discord.Interaction):
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
                queue_str = "\n".join([f"*{i}*. **{song}**" for i, song in enumerate(self.queue)])

        # create embed and send message
        emb = discord.Embed(title="**Current Queue**",
                            color=discord.Color.purple(),
                            description=queue_str)
        await interaction.response.send_message(embed=emb)

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