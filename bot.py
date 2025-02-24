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

bot = commands.Bot(command_prefix='h!',  # h! is bot command prefix for any bot actions
                   intents=intents)
logging.basicConfig(level=logging.INFO)


@bot.event
async def on_ready():
    logging.info("HibiscusBot is online!")
    bot.loop.create_task(node_connect())


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logging.info(f"Node {payload.node} is ready!")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    await payload.player.text_channel.send(f"Now playing: **{payload.track.title}** by "
                                           f"**{payload.track.author}** from "
                                           f""f"**{payload.track.source}"f"**")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    if not payload.player.queue.is_empty:
        next_track = payload.player.queue.get()
        await payload.player.play(next_track)
    else:
        await payload.player.text_channel.send(
            "Queue is empty. Add more songs to keep the music playing!")

# ---------------------------------------------------------------------------------------


async def node_connect():
    await bot.wait_until_ready()
    node: wavelink.Node = wavelink.Node(client=bot,
                                        identifier=os.getenv('NODE_ID'),
                                        uri=os.getenv('NODE_URI'),
                                        password=os.getenv('NODE_PASSWORD'))
    # Lavalink node from https://lavalink.appujet.site/ssl

    await wavelink.Pool.connect(client=bot, nodes=[node])


@bot.command(name="test", help="Responds with a simple message to test bot functionality")
async def test(ctx):
    response = "the test is working."
    await ctx.send(response)

# -----------------------------------------------------------------------------------------


@bot.command(name="play", help="requests a song to play")
async def play(ctx: commands.Context, *, search: str):  # playable searches all sources
    if not ctx.author.voice:  # ensure user is connected to voice channel
        return await ctx.send("You must be connected to a voice channel to play music!")

    if not ctx.voice_client:  # join the voice channel if the bot is not already in one
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = ctx.voice_client  # use existing voice client

    vc.text_channel = ctx.channel
    #  vc.autoplay = wavelink.AutoPlayMode.enabled  # enables autoplay, make function later

    try:  # search for the track
        tracks: list[wavelink.Playable] = await wavelink.Playable.search(search)
        if not tracks:
            return await ctx.send("No tracks found.")

        # Play the first track from the search results, change for playlists
        track = tracks[0]
        if not vc.playing:
            await vc.play(track)

        else:
            vc.queue.put(track)
            await ctx.send(f"Added to queue: **{track.title}** by **{track.author}** from "
                           f"**{track.source}**")
    except Exception as e:
        logging.error(f"Error playing track: {e}")
        await ctx.send("An error occurred while trying to play the track.")


@bot.command(name="pause", help="Pauses the current song")
async def pause(ctx: commands.Context):
    # Get the voice client (Player) for the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")

    if not vc.playing:
        return await ctx.send("No song is currently playing.")

    # Pause the player if it's not already paused
    if not vc.paused:
        await vc.pause(True)
        await ctx.send("Paused the current song.")
    else:
        await ctx.send("The song is already paused.")


@bot.command(name="resume", help="Resumes the current song")
async def resume(ctx: commands.Context):
    # Get the voice client (Player) for the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")

    # Resume the player if it's paused
    if vc.paused:
        await vc.pause(False)
        await ctx.send("Resumed the current song.")
    elif not vc.playing:
        await ctx.send("No song is currently playing.")  # double check this later
    else:
        await ctx.send("The song is not paused.")


@bot.command(name="queue", help="Returns the current music queue")
async def queue(ctx: commands.Context):
    # Get the player from the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await ctx.send("The queue is empty.")
    else:
        queue_list = "\n".join([f"{i + 1}. {track.title} by {track.author}" for i, track in
                                enumerate(vc.queue)])
        await ctx.send(f"Current queue:\n{queue_list}")


@bot.command(name="skip", help="Skips the song that is currently playing")
async def skip(ctx: commands.Context):
    # Get the player from the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await ctx.send("Skipped the current song.")
        await vc.stop()

    else:
        await vc.stop()
        await ctx.send("Skipped the current song.")


@bot.command(name="stop", help="Stops the current song and clears the queue")
async def stop(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")

    else:
        vc.queue.clear()
        await vc.stop()
        await ctx.send("Stopped the song and cleared the queue.")
        await vc.disconnect()


@bot.command(name="clear", help="Clears the queue")
async def clear(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await ctx.send("The queue is already empty.")
    else:
        vc.queue.clear()
        await ctx.send("Cleared the queue.")


@bot.command(name="shuffle", help="Shuffles the queue")
async def shuffle(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await ctx.send("The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await ctx.send("The queue is empty!")
    else:
        vc.queue.shuffle()
        await ctx.send("Shuffled the queue.")
        await queue(ctx)
# ------------------------------------------------------------------
bot.run(TOKEN)
