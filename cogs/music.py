# necessary imports
import discord
from discord import app_commands, commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio

# options
MY_GUILD = 1042652024598167552
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
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.voice = None
    
    # join voice channel
    @app_commands.command(name="join",
                        description="Joins a voice channel",)
    async def join(interaction: discord.Interaction):
        if interaction.user.voice:
            await interaction.response.send_message(f"Joining...")
            channel = interaction.user.voice.channel
            await channel.connect()
        else:
            await interaction.response.send_message(f"You must be in a voice channel to use this command!")

    # play command
    @app_commands.command(name="play",
                          description="Play audio from a youtube URL",)
    @app_commands.describe(url="URL of the video to play")
    async def play(interaction: discord.Interaction,
                url: str):
        await interaction.response.send_message(f"Attempting to play **{url}**")
        player = await YTDLSource.from_url(url, stream=True)
        guild = interaction.guild
        guild.voice_client.play(player, after=lambda e: print(f'Player error **{e}**') if e else None)

    # view queue command
    @app_commands.command(name="view_queue",
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
    @app_commands.command(name="skip",
                  description="Skips the current audio")
    async def skip(interaction: discord.Interaction):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.skip()
            await interaction.response.send_message(f"Skipped!")
        else:
            await interaction.response.send_message(f"Not currently in a voice channel!")


    # pause command
    @app_commands.command(name="pause",
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
    @app_commands.command(name = "resume",
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
    @app_commands.command(name = "stop",
                          description = "Stops audio")
    async def stop(interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message(f"Stopped audio!")
        else:
            await interaction.response.send_message(f"Not currently in a voice channel!")

    
# create setup
async def setup(bot):
    await bot.add_cog(Music(bot))