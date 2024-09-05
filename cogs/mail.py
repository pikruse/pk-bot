# necessary imports
import discord
from discord import app_commands
from discord.ext import commands
import os
import yt_dlp
import asyncio


# options
intents = discord.Intents.all()
mail_list = ["prod_pk"]

class Mail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="send_loops",
                          description="Send dropbox link for loops to a user")
    async def send_loops(self, interaction: discord.Interaction, link: str):
        

        return
    
    @app_commands.command(name="send_beats",
                          description="Send dropbox link for beats to a user")
    async def send_beats(self, interaction: discord.Interaction, link: str):
        return
    



# create setup function for cog
async def setup(bot):
    await bot.add_cog(Mail(bot))