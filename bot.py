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

# h! is bot command prefix for any bot actions
bot = commands.Bot(command_prefix='h!', intents=intents)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------------------


# sends basic one-line embeds so other functions are cleaner
async def embed_sender(text_channel: discord.TextChannel, message: str):
    embedVar = discord.Embed(description=message, color=0xE91E63)
    await text_channel.send(embed=embedVar)

# ---------------------------------------------------------------------------------------


@bot.event
async def on_ready():
    logging.info("HibiscusBot is online!")
    bot.loop.create_task(node_connect())


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logging.info(f"Node {payload.node} is ready!")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    embedVar = discord.Embed(color=0xE91E63)
    embedVar.add_field(name="Now Playing:", value=f"[**{payload.track.title}** by **{payload.track.author}**]"
                                                 f"({payload.track.uri})")
    embedVar.set_footer(text=f"Requested by {payload.original.requested}", icon_url=payload.original.requestedURL)

    await payload.player.text_channel.send(embed=embedVar)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    if not payload.player.queue.is_empty:
        next_track = payload.player.queue.get()
        await payload.player.play(next_track)
    else:
        embedVar = discord.Embed(description="Queue is empty. Add more songs to keep the music playing!",
                                 color=0xE91E63)
        await payload.player.text_channel.send(embed=embedVar)


@bot.event
async def on_wavelink_inactive_player(player: wavelink.Player):
    # no current plans to do anything other than even minutes for timeout, so casting this to an int is fine for now
    timeout_minutes = int(player.inactive_timeout/60)
    await embed_sender(text_channel=player.text_channel, message=f"The player has been inactive for {timeout_minutes} "
                                                                 f"minutes. Goodbye!")
    await player.disconnect()
# ---------------------------------------------------------------------------------------


async def node_connect():
    await bot.wait_until_ready()
    node: wavelink.Node = wavelink.Node(client=bot,
                                        identifier=os.getenv('NODE_ID'),
                                        uri=os.getenv('NODE_URI'),
                                        password=os.getenv('NODE_PASSWORD'))
    # Lavalink node from https://lavalink.appujet.site/ssl
    node._inactive_player_timeout = 300  # set the timeout limit in seconds
    await wavelink.Pool.connect(client=bot, nodes=[node])


@bot.command(name="test", help="testing embeds")
async def test(ctx: commands.Context):
    embedVar = discord.Embed(title="Test", description="Testing embedded messages")
    embedVar.add_field(name="Test Field 1", value="Testing embedded messages", inline=True)
    embedVar.add_field(name="Test Field 2", value="Testing embedded messages, inline", inline=True)
    embedVar.add_field(name="Test Field 3", value="Testing embedded messages, new line inline", inline=False)
    await ctx.send(embed=embedVar)


# -----------------------------------------------------------------------------------------


@bot.command(name="play", help="requests a song to play")
async def play(ctx: commands.Context, *, search: str):  # playable searches all sources
    if not ctx.author.voice:  # ensure user is connected to voice channel
        return await embed_sender(text_channel=ctx.channel,
                                  message=f"You must be connected to a voice channel to play music!")

    if not ctx.voice_client:  # join the voice channel if the bot is not already in one
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = ctx.voice_client  # use existing voice client

    vc.text_channel = ctx.channel  # add the channel the request was sent from

    #  vc.autoplay = wavelink.AutoPlayMode.enabled  # enables autoplay, make function later

    try:  # search for the track
        tracks: list[wavelink.Playable] = await wavelink.Playable.search(search)
        if not tracks:
            return await embed_sender(text_channel=ctx.channel, message=f"No tracks found for '{search}'")

        # Play the first track from the search results, change for playlists
        track = tracks[0]
        track.requested = ctx.author  # the user who requested the song
        track.requestedURL = ctx.author.avatar.url
        if not vc.playing:
            await vc.play(track)

        else:
            vc.queue.put(track)

            queue_embed = discord.Embed(title="Added to Queue:", color=0xE91E63)
            queue_embed.add_field(name="Track", value=f"[{track.title} by {track.author}]({track.uri})", inline=False)
            # add info about queue position
            queue_embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
            await ctx.send(embed=queue_embed)

    except Exception as e:
        logging.error(f"Error playing track: {e}")
        await embed_sender(text_channel=ctx.channel, message="An error occured while trying to play the track")


@bot.command(name="pause", help="Pauses the current song")
async def pause(ctx: commands.Context):
    # Get the voice client (Player) for the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    if not vc.playing:
        return await embed_sender(text_channel=ctx.channel, message="No song is currently playing.")

    # Pause the player if it's not already paused
    if not vc.paused:
        await vc.pause(True)
        await embed_sender(text_channel=ctx.channel, message="Paused the current song.")
    else:
        await embed_sender(text_channel=ctx.channel, message="The song is already paused.")


@bot.command(name="resume", help="Resumes the current song")
async def resume(ctx: commands.Context):
    # Get the voice client (Player) for the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    # Resume the player if it's paused
    if vc.paused:
        await vc.pause(False)
        await embed_sender(text_channel=ctx.channel, message="Resumed the current song.")
    elif not vc.playing:
        await embed_sender(text_channel=ctx.channel, message="No song is currently playing.")
    else:
        await embed_sender(text_channel=ctx.channel, message="The song is not currently paused.")


@bot.command(name="queue", help="Returns the current music queue")
async def queue(ctx: commands.Context):
    # Get the player from the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is empty.")
    else:
        embedVar = discord.Embed(title="Upcoming Queue:", color=0xE91E63)
        queue_description = ""

        for i, track in enumerate(vc.queue, start=1):
            # Use one queue description instead of creating new fields to avoid space needed for empty name
            queue_description += f"**{i}**) [**{track.title}** by **{track.author}**]({track.uri})\n"

        embedVar.add_field(name='\u200b', value=queue_description, inline=False)
        await ctx.send(embed=embedVar)


@bot.command(name="skip", help="Skips the song that is currently playing")
async def skip(ctx: commands.Context):
    # Get the player from the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    else:
        await embed_sender(text_channel=ctx.channel, message="Skipped the current song.")
        await vc.stop()  # stop after sending the skip message so the empty queue message comes last


@bot.command(name="stop", help="Stops the current song and clears the queue")
async def stop(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    else:
        # these two lines are necessary before disconnected to ensure no errors
        vc.queue.clear()
        await vc.stop()

        await embed_sender(text_channel=ctx.channel, message="Stopped the current song and cleared the queue")
        await vc.disconnect()


@bot.command(name="clear", help="Clears the queue")
async def clear(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is already empty.")

    else:
        vc.queue.clear()
        await embed_sender(text_channel=ctx.channel, message="Cleared the queue")


@bot.command(name="shuffle", help="Shuffles the queue")
async def shuffle(ctx: commands.Context):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is empty!")

    else:
        vc.queue.shuffle()
        await embed_sender(text_channel=ctx.channel, message="Shuffled the queue")
        await queue(ctx)  # call queue to print the newly shuffled queue
# ------------------------------------------------------------------
bot.run(TOKEN)
