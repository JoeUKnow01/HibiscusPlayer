# bot.py
import os
import logging
import discord
from dotenv import load_dotenv
from discord.ext import commands

import wavelink

intents = discord.Intents.all()
intents.default()
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_SERVER')  # Discord Servers are actually called Guilds

client = discord.Client(intents=intents)

bot = commands.Bot(command_prefix='h!',
				   intents=intents)  # h! is bot command prefix for any bot actions
logging.basicConfig(level=logging.INFO)

@bot.event
async def on_ready():
	logging.info("HibiscusBot is online!")
	bot.loop.create_task(node_connect())


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
	logging.info(f"Node {payload.node} is ready!")


async def node_connect():
	await bot.wait_until_ready()
	node: wavelink.Node = wavelink.Node(client=bot,  # figure out why connection failure
										identifier="Public Lavalink v4",
										uri="wss://lava-v4.ajieblogs.eu.org:443", # wss means secure
										password="https://dsc.gg/ajidevserver")

	await wavelink.Pool.connect(client=bot, nodes=[node])

# Lavalink node from https://lavalink.appujet.site/ssl
# {
#  "identifier": "Public Lavalink v4",
#  "password": "https://dsc.gg/ajidevserver",
#  "host": "lava-v4.ajieblogs.eu.org",
#  "port": 443,
#  "secure": true
# }


@bot.command(name="test", help="Responds with a simple message to test bot functionality")
async def test(ctx):
	response = "the test is working."
	await ctx.send(response)


@bot.command(name="play", help="requests a song to play")
async def play(ctx: commands.Context, *, search: str):  # playable searches all sources
	if not ctx.voice_client:
		vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
	elif not ctx.author.voice:
		return await ctx.send("You must be connected to a voice channel to play music.")
	
		# Search for the track
	try:
		tracks: list[wavelink.player] = await wavelink.player.search(search)
		if not tracks:
			return await ctx.send("No tracks found.")

		# Play the first track from the search results
		track = tracks[0]
		await vc.play(track)
		await ctx.send(f"Now playing: **{track.title}** by **{track.author}**")
	except Exception as e:
		logging.error(f"Error playing track: {e}")
		await ctx.send("An error occurred while trying to play the track.")


bot.run(TOKEN)
