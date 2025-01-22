# bot.py
import os

import discord
from dotenv import load_dotenv
from discord.ext import commands

intents = discord.Intents.all()
intents.default()
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_SERVER') # Discord Servers are actually called Guilds

client = discord.Client(intents = intents)

bot = commands.Bot(command_prefix = 'h!' , intents=intents) # h! is bot command prefix for any bot actions


@bot.command(name="test", help = "Responds with a simple message to test bot functionality")
async def test(ctx):
    response = "the test is working."
    await ctx.send(response)
bot.run(TOKEN)