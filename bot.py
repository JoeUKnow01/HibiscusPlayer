# bot.py
import os

import discord
from dotenv import load_dotenv
from discord.ext import commands

import wavelink


intents = discord.Intents.all()
intents.default()
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_SERVER') # Discord Servers are actually called Guilds

client = discord.Client(intents = intents)

bot = commands.Bot(command_prefix = 'h!' , intents=intents) # h! is bot command prefix for any bot actions

@bot.event
async def on_ready():
    print("HibiscusBot is online!")
    bot.loop.create_task(node_connect())

@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    print(f"Node {node.identifier} is ready! ")

async def node_connect():
    await bot.wait_until_ready()
    await wavelink.NodePool.create_node( bot=bot, #figure out why connection failure
                                         identifier="Catfein DE",
                                         host="lavalink.alfari.id",
                                         port=443,
                                         password="catfein",
                                         https=True)
#Lavalink node from https://lavalink.appujet.site/ssl
#{
 # "identifier": "Catfein DE",
 # "password": "catfein",
 # "host": "lavalink.alfari.id",
 # "port": 443,
 # "secure": true
#}

@bot.command(name="test", help = "Responds with a simple message to test bot functionality")
async def test(ctx):
    response = "the test is working."
    await ctx.send(response)

@bot.command(name="play", help= "requests a song to play")
async def play(ctx: commands.Context, *, search: wavelink.YouTubeTrack):
    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    elif not ctx.author.voice_client:
        return await ctx.send("You must be connected to a voice channel to play music.")
    else:
        vc: wavelink.Player = ctx.voice_client

    vc.play(search)

bot.run(TOKEN)