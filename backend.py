import os
import discord
import wavelink
import time
from discord.ext import commands
import requests
import threading
import sys
import asyncio
import json
from urllib.parse import urlparse, parse_qs

bot_status = {
    'status': 'Initializing',
    'track': None,
    'position': 0,
    'duration': 0
}

port = None
host = None
password = None
discord_user_token = None
voice_channel = None
music_query = None
volume = 100 
prefix = "."

client = None
bot_initialized = False

def load_config():
    global port, host, password, discord_user_token, voice_channel, music_query, volume
    try:
        with open("music.json", "r") as f:
            settings = json.load(f)
            port = settings["port"]
            host = settings["host"]
            password = settings["password"]
    except Exception as e:
        log(f"Error loading music.json: {e}", "error")
        return False

    try:
        with open("bot_config.json", "r") as f:
            config = json.load(f)
            discord_user_token = config["discord_user_token"]
            voice_channel = config["voice_channel"]
            music_query = config["music_query"]
            volume = config["volume"]
            discord.http.Route.BASE = "https://discord.com/api/v9"
        return True
    except FileNotFoundError:
        bot_status['status'] = 'Waiting for configuration'
        log("Bot config not found. Please run the web interface first.", "warning")
        return False
    except Exception as e:
        bot_status['status'] = f'Error loading config: {str(e)}'
        log(f"Error loading bot_config.json: {e}", "error")
        return False

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def title(topic: any):
    if os.name == 'nt':
        os.system(f"title {topic}")

def get_status():
    return bot_status

def validate_token(token):
    if not token:
        return False
    try:
        response = requests.get("https://canary.discord.com/api/v10/users/@me", headers={"Authorization": token})
        is_valid = response.status_code in [200, 201, 204]
        if not is_valid:
            bot_status['status'] = f'Invalid token (Status: {response.status_code})'
        return is_valid
    except Exception as e:
        bot_status['status'] = f'Token validation error: {str(e)}'
        return False

class MusicSelfbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_vc = None
        self.current_track = None
        self.playing = False

    @commands.Cog.listener()
    async def on_connect(self):
        log(f"{self.bot.user} Connected to Discord", "info")
        log("Connecting to voice channel...", "info")
        
        try:
            # Connect to Lavalink node
            await wavelink.NodePool.create_node(bot=self.bot, host=host, port=port, password=password)
            log("Connected to music server", "info")
            
            # Connect to voice channel
            connection_success = await self.connect_vc()
            if not connection_success:
                log("Failed to connect to voice channel", "error")
                bot_status['status'] = 'Error: Failed to connect to voice channel'
                return
                
            # Start playing music
            await self.play_next_song()
        except Exception as e:
            log(f"Error in on_connect: {e}", "error")
            bot_status['status'] = f'Error: {str(e)}'

    async def connect_vc(self):
        try:
            channel = self.bot.get_channel(int(voice_channel))
            if channel is None:
                log(f"Voice channel with ID {voice_channel} not found. Make sure the ID is correct and the bot has access to it.", "error")
                bot_status['status'] = f"Error: Voice channel {voice_channel} not found"
                return False
                
            self.current_vc: wavelink.Player = await channel.connect(cls=wavelink.Player)
            log(f"Connected to voice channel: {channel.name}", "success")
            return True
        except Exception as e:
            log(f"Error connecting to voice channel: {e}", "error")
            bot_status['status'] = f"Error: {str(e)}"
            return False

    async def filters(self, ctx, player, filter):
        if filter == "nightcore":
            await player.set_filter(wavelink.Equalizer.boost(0.3))
            await ctx.send("Nightcore filter has been enabled.")
        elif filter == "bass":
            await player.set_filter(wavelink.Equalizer.boost(0.3))
            await ctx.send("Bass filter has been enabled.")
        elif filter == "vaporwave":
            await player.set_filter(wavelink.Equalizer.boost(0.3))
            await ctx.send("Vaporwave filter has been enabled.")
        elif filter == "clear":
            await player.set_filter(None)
            await ctx.send("Filters have been cleared.")
        else:
            await ctx.send("Invalid filter. Available filters: nightcore, bass, vaporwave, clear")

    async def play_next_song(self):
        global bot_status, music_query
        self.playing = False
        
        # Check if we have a valid voice channel connection
        if not self.current_vc:
            log("Cannot play music: Not connected to a voice channel", "error")
            bot_status['status'] = 'Error: Not connected to a voice channel'
            return
            
        song_name = music_query
        log(f"Searching for: {song_name}", "info")
        bot_status['status'] = 'Searching'
        
        try:
            # Try to find the song
            youtube_id = extract_youtube_id(song_name)
            if youtube_id:
                log(f"Found YouTube ID: {youtube_id}", "info")
                query = f"https://www.youtube.com/watch?v={youtube_id}"
                # Use a task for the search to handle timeouts properly
                search_task = asyncio.create_task(wavelink.YouTubeTrack.search(query=query, return_first=True))
                try:
                    song = await asyncio.wait_for(search_task, timeout=15.0)
                except asyncio.TimeoutError:
                    log("Search timed out", "error")
                    bot_status['status'] = 'Error: Search timed out'
                    return
            else:
                log("Searching YouTube...", "info")
                # Use a task for the search to handle timeouts properly
                search_task = asyncio.create_task(wavelink.YouTubeTrack.search(query=song_name))
                try:
                    songs = await asyncio.wait_for(search_task, timeout=15.0)
                    if not songs:
                        log(f"No results found for: {song_name}", "error")
                        bot_status['status'] = 'Error: No results found'
                        return
                    song = songs[0]
                except asyncio.TimeoutError:
                    log("Search timed out", "error")
                    bot_status['status'] = 'Error: Search timed out'
                    return
                
            # Play the song
            log(f"Playing: {song.title} by {song.author}", "success")
            play_task = asyncio.create_task(self.current_vc.play(song))
            volume_task = asyncio.create_task(self.current_vc.set_volume(100))
            
            try:
                await asyncio.wait_for(play_task, timeout=10.0)
                await asyncio.wait_for(volume_task, timeout=5.0)
            except asyncio.TimeoutError:
                log("Timeout while trying to play the song", "error")
                bot_status['status'] = 'Error: Timeout while playing'
                return
            
            # Update status
            self.current_track = song
            self.playing = True
            bot_status['status'] = 'Playing'
            bot_status['track'] = {
                'title': song.title,
                'author': song.author,
                'url': song.uri,
                'thumbnail': f"https://img.youtube.com/vi/{extract_youtube_id(song.uri)}/hqdefault.jpg" if extract_youtube_id(song.uri) else None
            }
            
            # Start updating the console
            console_update_task = asyncio.create_task(self.update_console())
            
        except Exception as e:
            error_msg = f"Error while searching or playing the track: {e}"
            log(error_msg, "error")
            bot_status['status'] = f'Error: {str(e)}'

    async def update_console(self):
        global bot_status
        try:
            while self.playing:
                try:
                    # Check if we still have a valid connection
                    if not self.current_vc or not self.current_track:
                        self.playing = False
                        break
                        
                    # Get the current position and duration
                    position = self.current_vc.position // 1000
                    duration = self.current_track.length // 1000
                    pos_mins, pos_secs = divmod(position, 60)
                    dur_mins, dur_secs = divmod(duration, 60)
                    
                    # Update the status
                    bot_status['position'] = position
                    bot_status['duration'] = duration
                    song_info = f"[{pos_mins:02}:{pos_secs:02} | {dur_mins:02}:{dur_secs:02}] -> {self.current_track.title}"
                    bot_status['status'] = f'Playing: {song_info}'
                    
                    # Use a timeout-safe sleep
                    try:
                        await asyncio.wait_for(asyncio.sleep(1), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                        
                except Exception as e:
                    log(f"Error updating console: {e}", "error")
                    await asyncio.sleep(1)
        except Exception as e:
            log(f"Error in update_console loop: {e}", "error")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track, reason):
        if reason == 'FINISHED':
            await self.play_next_song()

def extract_youtube_id(url):
    parsed_url = urlparse(url)
    if parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    elif parsed_url.hostname == "youtu.be":
        return parsed_url.path[1:]
    return None

def start_bot():
    global bot_status, client, bot_initialized
    if not load_config():
        return False
    if not validate_token(discord_user_token):
        log("Invalid token.........", "error")
        return False
    bot_status['status'] = 'Starting'
    log(f"Starting bot with music: {music_query}", "info")
    log(f"Connecting to voice channel: {voice_channel}", "info")
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except:
            pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = commands.Bot(command_prefix=prefix, case_insensitive=False, self_bot=True, intents=discord.Intents.all())
        client.add_cog(MusicSelfbot(client))
        bot_status['status'] = 'Connecting to Discord'
        loop.create_task(client.start(discord_user_token, bot=False))
        bot_thread = threading.Thread(target=loop.run_forever)
        bot_thread.daemon = True
        bot_thread.start()
        bot_initialized = True
        return True
    except Exception as e:
        bot_status['status'] = f'Error: {str(e)}'
        log(f"Error starting bot: {e}", "error")
        return False

def stop():
    global bot_status, client, bot_initialized
    bot_status['status'] = 'Stopping'
    try:
        if client:
            # Get the event loop that was created when starting the bot
            try:
                # Try to get the running event loop from the client's loop
                loop = client.loop
                if not loop or not loop.is_running():
                    log("No running event loop found, creating a new one", "warning")
                    loop = None
            except Exception:
                loop = None
                
            # If we couldn't get a running loop, find or create one
            if loop is None:
                try:
                    # Try to get the current event loop
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    # If there's no event loop in this thread, create a new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            
            # First try to leave voice channel if connected
            try:
                cog = client.get_cog('MusicSelfbot')
                if cog and cog.current_vc:
                    log("Leaving voice channel...", "info")
                    
                    # Create a task to disconnect from voice channel
                    async def leave_voice():
                        try:
                            await cog.current_vc.disconnect()
                            log("Left voice channel successfully", "success")
                        except Exception as e:
                            log(f"Error leaving voice channel: {e}", "error")
                    
                    # Run the coroutine in the event loop
                    if loop.is_running():
                        # If loop is running, use run_coroutine_threadsafe
                        future = asyncio.run_coroutine_threadsafe(leave_voice(), loop)
                        try:
                            future.result(timeout=5)
                        except Exception as e:
                            log(f"Timeout or error while leaving voice channel: {e}", "warning")
                    else:
                        # If loop is not running, use run_until_complete
                        try:
                            loop.run_until_complete(leave_voice())
                        except Exception as e:
                            log(f"Error in run_until_complete for leaving voice channel: {e}", "error")
            except Exception as e:
                log(f"Error while trying to leave voice channel: {e}", "error")
            
            # Then close the client
            log("Closing Discord client...", "info")
            try:
                # Create a task to close the client
                async def close_client():
                    try:
                        await client.close()
                        log("Discord client closed successfully", "success")
                    except Exception as e:
                        log(f"Error closing client: {e}", "error")
                
                # Run the coroutine in the event loop
                if loop.is_running():
                    # If loop is running, use run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(close_client(), loop)
                    try:
                        future.result(timeout=5)
                    except Exception as e:
                        log(f"Timeout or error while closing client: {e}", "warning")
                else:
                    # If loop is not running, use run_until_complete
                    try:
                        loop.run_until_complete(close_client())
                    except Exception as e:
                        log(f"Error in run_until_complete for closing client: {e}", "error")
            except Exception as e:
                log(f"Error while closing Discord client: {e}", "error")
        
        # Stop the event loop if it's running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except Exception as e:
            log(f"Error stopping event loop: {e}", "warning")
        
        bot_status['status'] = 'Stopped'
        bot_status['track'] = None
        bot_initialized = False
        log("Bot stopped successfully", "success")
        return True
    except Exception as e:
        log(f"Error stopping bot: {e}", "error")
        return False

def start_bot_with_config(config):
    global bot_status, client, bot_initialized, discord_user_token, voice_channel, music_query, volume
    try:
        with open("music.json", "r") as f:
            settings = json.load(f)
            global port, host, password
            port = settings["port"]
            host = settings["host"]
            password = settings["password"]
    except Exception as e:
        log(f"Error loading music.json: {e}", "error")
        bot_status['status'] = f'Error loading music server settings: {str(e)}'
        return False
    try:
        discord_user_token = config["discord_user_token"]
        voice_channel = config["voice_channel"]
        music_query = config["music_query"]
        volume = config["volume"]  
        discord.http.Route.BASE = "https://discord.com/api/v9"
    except KeyError as e:
        bot_status['status'] = f'Missing configuration key: {str(e)}'
        log(f"Missing configuration key: {e}", "error")
        return False
    if not validate_token(discord_user_token):
        log("Invalid token.........", "error")
        return False
    bot_status['status'] = 'Starting'
    log(f"Starting bot with music: {music_query}", "info")
    log(f"Connecting to voice channel: {voice_channel}", "info")
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except:
            pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = commands.Bot(command_prefix=prefix, case_insensitive=False, self_bot=True, intents=discord.Intents.all())
        client.add_cog(MusicSelfbot(client))
        bot_status['status'] = 'Connecting to Discord'
        loop.create_task(client.start(discord_user_token, bot=False))
        bot_thread = threading.Thread(target=loop.run_forever)
        bot_thread.daemon = True
        bot_thread.start()
        bot_initialized = True
        return True
    except Exception as e:
        bot_status['status'] = f'Error: {str(e)}'
        log(f"Error starting bot: {e}", "error")
        return False

log_callback = None

def log(message, log_type='default'):
    timestamp = time.strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    if log_callback:
        log_callback(message, log_type)

def setup_logging(callback):
    global log_callback
    log_callback = callback
    log("Logging system initialized", "info")

if __name__ == "__main__":
    start_bot()