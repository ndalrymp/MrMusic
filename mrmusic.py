import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    voice_clients = {}
    song_queues = {}
    volume_settings = {}

    yt_dlp_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dlp_options)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    async def play_next(guild_id):
        """Play the next song in the queue."""
        if guild_id in song_queues and song_queues[guild_id]:
            next_song = song_queues[guild_id].pop(0)
            song_url = next_song['url']
            voice_client = voice_clients[guild_id]
            player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)

            def after_playing(error):
                if error:
                    print(f"Error during playback: {error}")
                asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop)

            voice_client.play(player, after=after_playing)
        else:
            # Only disconnect when the queue is empty after finishing playback
            if guild_id in voice_clients:
                await voice_clients[guild_id].disconnect()
                del voice_clients[guild_id]
                del song_queues[guild_id]

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    @client.event
    async def on_message(message):
        if message.author.bot:
            return
        
        if message.content.startswith("?help"):
            help_text = "\n".join([
            "Available Commands:",
            "- **?play [url]**: Play a song from a URL (YouTube, etc.)",
            "- **?queue**: Show the current song queue",
            "- **?skip**: Skip the current song",
            "- **?pause**: Pause the current song",
            "- **?resume**: Resume the current song",
            "- **?stop**: Stop playback and disconnect the bot",
        ])
            await message.channel.send(help_text)

        elif message.content.startswith("?play"):
            try:
                url = message.content.split()[1]
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                song_url = data['url']
                song_title = data['title']

                if message.guild.id not in song_queues:
                    song_queues[message.guild.id] = []

                # Store the song with title and URL
                song_queues[message.guild.id].append({'url': song_url, 'title': song_title})

                if not voice_clients.get(message.guild.id) or not voice_clients[message.guild.id].is_playing():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client
                    await play_next(message.guild.id)
                else:
                    await message.channel.send(f"**{song_title}** added to the queue!")

            except Exception as e:
                print(f"Error adding song to queue: {e}")

        elif message.content.startswith("?queue"):
            if message.guild.id in song_queues and song_queues[message.guild.id]:
                # Display the title in the queue list
                queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(song_queues[message.guild.id])])
                await message.channel.send(f"Current Queue:\n{queue_list}")
            else:
                await message.channel.send("The queue is empty!")

        elif message.content.startswith("?skip"):
            try:
                if voice_clients.get(message.guild.id) and voice_clients[message.guild.id].is_playing():
                    voice_clients[message.guild.id].stop()  # This triggers the `after` callback
                else:
                    await message.channel.send("No song is currently playing!")
            except Exception as e:
                print(f"Error skipping song: {e}")

        elif message.content.startswith("?pause"):
            try:
                if voice_clients.get(message.guild.id):
                    voice_clients[message.guild.id].pause()
            except Exception as e:
                print(f"Error pausing playback: {e}")

        elif message.content.startswith("?resume"):
            try:
                if voice_clients.get(message.guild.id):
                    voice_clients[message.guild.id].resume()
            except Exception as e:
                print(f"Error resuming playback: {e}")

        elif message.content.startswith("?stop"):
            try:
                if voice_clients.get(message.guild.id):
                    voice_clients[message.guild.id].stop()
                    await voice_clients[message.guild.id].disconnect()
                    del voice_clients[message.guild.id]
                    del song_queues[message.guild.id]
            except Exception as e:
                print(f"Error stopping playback: {e}")

    client.run(TOKEN)