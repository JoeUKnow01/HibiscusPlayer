# bot.py
import asyncio
import os
import math
import logging

import discord
from dotenv import load_dotenv
from discord.ext import commands
from pagination import PaginationView

import wavelink

intents = discord.Intents.all()
intents.default()
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_SERVER')  # Discord Servers are actually called Guilds

# h! is bot command prefix for any bot actions
bot = commands.Bot(command_prefix='h!', intents=intents, reconnect=True)
logging.basicConfig(level=logging.DEBUG,    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='[%Y-%m-%d] %H:%M:%S')

########################################################################################################################


# sends basic one-line embeds so other functions are cleaner
async def embed_sender(text_channel: discord.TextChannel, message: str):
    embedVar = discord.Embed(description=message, color=0xE91E63)
    await text_channel.send(embed=embedVar)


########################################################################################################################


@bot.event
async def on_ready():
    logging.info("HibiscusBot is online!")
    logging.info(f"Gateway latency is {bot.latency * 1000:.2f}ms")
    bot.loop.create_task(node_connect())


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logging.info(f"{payload.node} is ready!")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    embedVar = discord.Embed(color=0x2ecc71)
    embedVar.add_field(name="Now Playing:", value=f"[**{payload.track.title}** by **{payload.track.author}**]"
                                                  f"({payload.track.uri})")
    embedVar.set_footer(text=f"Requested by {payload.original.requested}", icon_url=payload.original.requestedURL)

    await payload.player.text_channel.send(embed=embedVar)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    try:
        bot_queue = payload.player.queue
        bot_text = payload.player.text_channel
    except AttributeError:
        logging.warning(msg="Queue doesn't exist in on_wavelink_track_end. This is likely due to forced disconnect.")
        return
    if not bot_queue.is_empty:
        next_track = payload.player.queue.get()
        await payload.player.play(next_track)
    else:
        await embed_sender(text_channel=bot_text, message="Queue is empty. Add more songs to keep the music playing!")


@bot.event
async def on_wavelink_inactive_player(player: wavelink.Player):
    # no current plans to do anything other than even minutes for timeout, so casting this to an int is fine for now
    timeout_minutes = int(player.inactive_timeout / 60)
    await embed_sender(text_channel=player.text_channel, message=f"The player has been inactive for {timeout_minutes} "
                                                                 f"minutes. Goodbye!")
    await player.disconnect(force=True)  # Ensure cleanup with a forced disconnect
    logging.info(f"The bot has disconnected from {player.channel} in {player.guild} due to inactivity.")
    await asyncio.sleep(0)  # Yield control to the event loop (attempt to fix bug)


# This function is called whenever there is an update to the voice channel.
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Check if the bot was forcefully disconnected here later. Figure out how to make that work.
    if member.id == bot.user.id and before.channel and not after.channel:
        logging.info(f"Bot was disconnected from a voice channel in guild {member.guild.name}.")

        # Clean up the voice client for the specific guild
        vc: wavelink.Player = member.guild.voice_client
        if vc:
            await vc.disconnect(force=True)
            logging.info(f"Cleaned up voice client in guild {member.guild.name}.")
########################################################################################################################


async def node_connect():
    await bot.wait_until_ready()
    node: wavelink.Node = wavelink.Node(client=bot,
                                        identifier=os.getenv('NODE_ID'),
                                        uri=os.getenv('NODE_URI'),
                                        password=os.getenv('NODE_PASSWORD'))
    # Lavalink node from https://lavalink.appujet.site/ssl
    node._inactive_player_timeout = 180  # set the timeout limit in seconds
    await wavelink.Pool.connect(client=bot, nodes=[node])


@bot.command(name="test", help="testing embeds")
async def test(ctx: commands.Context):
    embedVar = discord.Embed(title="Test", description="Testing embedded messages")
    embedVar.add_field(name="Test Field 1", value="Testing embedded messages", inline=True)
    embedVar.add_field(name="Test Field 2", value="Testing embedded messages, inline", inline=True)
    embedVar.add_field(name="Test Field 3", value="Testing embedded messages, new line inline", inline=False)
    await ctx.send(embed=embedVar)


@bot.command(name="testpage", help="testing embedded messages w/ pagination")
async def testpage(ctx: commands.Context):
    embeds = [
        discord.Embed(title="Page 1", description="This is the first page."),
        discord.Embed(title="Page 2", description="This is the second page."),
        discord.Embed(title="Page 3", description="This is the third page."),
    ]

    # Send the first embed with the pagination view
    view = PaginationView(embeds)
    await ctx.send(embed=embeds[0], view=view)
########################################################################################################################
# Play commands with track options (i.e. skip, pause)


@bot.command(name="play", aliases=['p'], help="requests a song to play")
async def play(ctx: commands.Context, *, search: str, queue_next=False):  # playable searches all sources
    if not ctx.author.voice:  # ensure user is connected to voice channel
        return await embed_sender(text_channel=ctx.channel,
                                  message=f"You must be connected to a voice channel to play music!")

    if not ctx.voice_client:  # join the voice channel if the bot is not already in one
        try:
            logging.info(msg=f"Trying to connect to {ctx.author.voice.channel} in {ctx.guild}...")

            # Check if the node is connected
            node = wavelink.Pool.get_node()
            logging.info(f"Wavelink node status: {node.status}")

            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            logging.info(msg=f"Successfully connected to {ctx.author.voice.channel} in {ctx.guild}.")
        except asyncio.CancelledError as e:
            logging.error(f"CancelledError when trying to connect to voice channel: {e}")
            raise
        except Exception as e:
            logging.error(f"Error Joining the voice channel: {e}")
            return await embed_sender(text_channel=ctx.channel,
                                      message="An error occurred while trying to join the channel.")
    else:
        vc: wavelink.Player = ctx.voice_client  # use existing voice client

    vc.text_channel = ctx.channel  # add the channel the request was sent from

    #  vc.autoplay = wavelink.AutoPlayMode.enabled  # enables autoplay, make function later

    try:  # search for the track, default is YouTube but can be changed
        tracks: list[wavelink.Playable] = await wavelink.Playable.search(search)
        if not tracks:
            return await embed_sender(text_channel=ctx.channel, message=f"No tracks found for '{search}'")

        # Play single tracks
        if type(tracks) is not wavelink.tracks.Playlist:
            track = tracks[0]
            logging.info(f"Found single track for {ctx.author} in {ctx.guild}")

            track.requested = ctx.author  # the user who requested the song
            track.requestedURL = ctx.author.avatar.url  # the avatar of the user, for flavoring the footer
            if not vc.playing:
                return await vc.play(track)

            else:
                if queue_next:
                    vc.queue.put_at(0, track)
                    queue_embed = discord.Embed(title="Playing next:", color=0xE91E63)
                else:
                    vc.queue.put(track)
                    queue_embed = discord.Embed(title="Added to Queue:", color=0xE91E63)
                queue_embed.add_field(name="Track", value=f"[{track.title} by {track.author}]({track.uri})", inline=False)
                # add info about queue position
                queue_embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
                return await ctx.send(embed=queue_embed)

        # Play playlists
        else:
            playlist = tracks
            logging.info(f"Found a playlist for {ctx.author} in {ctx.guild}")

            # set the necessary data for the track start embed
            for track in playlist:
                track.requested = ctx.author
                track.requestedURL = ctx.author.avatar.url

            # add the songs to the queue
            if queue_next:
                await embed_sender(text_channel=ctx.channel, message="You can't play an entire playlist next! Added to "
                                                                     "end of queue.")
            vc.queue.put(playlist)
            playlist_embed = discord.Embed(title="Added playlist to Queue:", color=0xE91E63)

            playlist_embed.add_field(name=f"{playlist.name}", value=f"{len(playlist.tracks)} songs", inline=False)
            playlist_embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
            await ctx.send(embed=playlist_embed)

            # if nothing is playing, begin to play the queue
            if not vc.playing:
                return await vc.play(vc.queue[0])
            return

    except Exception as e:
        logging.error(f"Error playing track: {e}")
        await embed_sender(text_channel=ctx.channel, message="An error occured while trying to play the track")


@bot.command(name="playnext", aliases=['pn'], help="Puts a song at the top of the queue")
async def playnext(ctx: commands.Context, search: str):
    await play(ctx, search=search, queue_next=True)


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
        await vc.disconnect(force=True)  # Ensure cleanup with a forced disconnect

########################################################################################################################
# Queue commands


@bot.command(name="queue", aliases=['q'], help="Returns the current music queue")
async def queue(ctx: commands.Context):
    # Get the player from the guild
    vc: wavelink.Player = ctx.voice_client

    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is empty.")
    else:
        # Calculate the number of pages needed
        queue_len = len(vc.queue)
        songs_per_page = 10
        pages_needed = math.ceil(queue_len / songs_per_page)

        embed_pages = []
        for page in range(pages_needed):
            queue_embed = discord.Embed(title="Upcoming Queue:", color=0xE91E63)
            queue_embed.set_footer(text=f"Page {page + 1}/{pages_needed}")

            # Add songs for the current page
            start_index = page * songs_per_page
            end_index = start_index + songs_per_page

            for i, track in enumerate(vc.queue[start_index:end_index], start=start_index + 1):
                queue_embed.add_field(name='\u200b',
                                      value=f"**{i}**) [**{track.title}** by **{track.author}**]({track.uri})\n",
                                      inline=False
                                      )

            embed_pages.append(queue_embed)
        view = PaginationView(embed_pages)
        await ctx.send(embed=embed_pages[0], view=view)


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


@bot.command(name="move", help="Move the position of a track in queue")
async def move(ctx: commands.Context, from_pos: int, to_pos: int):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")

    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is empty!")

    elif from_pos > len(vc.queue):
        await embed_sender(text_channel=ctx.channel, message="Invalid 'from' position!")

    elif to_pos > len(vc.queue):
        await embed_sender(text_channel=ctx.channel, message="Invalid 'to' position!")

    else:
        moving_track = vc.queue.get_at(from_pos - 1)  # queue positions start at 1 externally but 0 internally
        vc.queue.put_at(to_pos - 1, moving_track)
        await embed_sender(text_channel=ctx.channel, message=f"Moved {moving_track} from {from_pos} -> {to_pos} "
                                                             f"in queue.")


@bot.command(name="remove", help="Remove a track from queue")
async def remove(ctx: commands.Context, track_position: int):
    vc: wavelink.Player = ctx.voice_client
    if not vc:
        return await embed_sender(text_channel=ctx.channel, message="The bot is not connected to a voice channel.")
    elif vc.queue.is_empty:
        await embed_sender(text_channel=ctx.channel, message="The queue is empty!")
    else:
        to_remove_track = vc.queue.get_at(track_position - 1)  # pops it out of queue so no need to delete
        await embed_sender(text_channel=ctx.channel, message=f"Removed {to_remove_track} from queue.")
########################################################################################################################
bot.run(TOKEN)
