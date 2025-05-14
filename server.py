from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import json
import threading
import importlib
import sys

app = Flask(__name__)

music_bot = None
bot_thread = None

logs = []
max_logs = 100

@app.route('/')
def index():
    return render_template('i.html')

@app.route('/api/play', methods=['POST'])
def play_music():
    global music_bot, bot_thread
    data = request.json
    token = data.get('token')
    channel_id = data.get('channelId')
    music = data.get('music')
    if not token or not channel_id or not music:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    try:
        settings = {
            "discord_user_token": token,
            "voice_channel": channel_id,
            "music_query": music,
            "volume": 100
        }
        if music_bot and hasattr(music_bot, 'stop'):
            music_bot.stop()
        if 'backend' in sys.modules:
            importlib.reload(sys.modules['backend'])
        else:
            import backend
        music_bot = sys.modules['backend']
        add_log(f"Starting bot with token: ***{token[-5:]}, channel: {channel_id}, music: {music}", "info")
        success = music_bot.start_bot_with_config(settings)
        if success:
            return jsonify({'success': True, 'message': 'Music bot started successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to start music bot. Check server logs.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

def start_bot():
    global music_bot
    try:
        if 'backend' in sys.modules:
            importlib.reload(sys.modules['backend'])
        else:
            import backend
        music_bot = sys.modules['backend']
        return True
    except Exception as e:
        add_log(f"Error starting music bot: {e}", "error")
        return False

@app.route('/api/status', methods=['GET'])
def get_status():
    global music_bot
    if music_bot and hasattr(music_bot, 'get_status'):
        status = music_bot.get_status()
        return jsonify(status)
    else:
        return jsonify({'status': 'Server running, bot not initialized', 'track': None})

@app.route('/api/stop', methods=['POST'])
def stop_music():
    global music_bot
    if music_bot and hasattr(music_bot, 'stop'):
        add_log("Stopping music and leaving voice channel", "info")
        success = music_bot.stop()
        if success:
            return jsonify({'success': True, 'message': 'Music stopped and left voice channel'})
        else:
            return jsonify({'success': False, 'message': 'Failed to stop music'})
    else:
        return jsonify({'success': False, 'message': 'Bot not initialized'}), 400

@app.route('/api/logs', methods=['GET'])
def get_logs():
    global logs
    return jsonify({'logs': logs})

def add_log(message, log_type='default'):
    global logs, max_logs
    timestamp = time.strftime("%H:%M:%S")
    log_entry = {
        'message': f"[{timestamp}] {message}",
        'type': log_type,
        'timestamp': timestamp
    }
    logs.append(log_entry)
    if len(logs) > max_logs:
        logs.pop(0)
    print(f"LOG: {log_entry['message']}")

def capture_backend_log(message, log_type='default'):
    add_log(message, log_type)

if __name__ == '__main__':
    import sys
    import time
    logs.append({
        'message': f"[{time.strftime('%H:%M:%S')}] Server starting...",
        'type': 'info',
        'timestamp': time.strftime('%H:%M:%S')
    })
    print(f"[{time.strftime('%H:%M:%S')}] Server starting...")
    import backend
    backend.setup_logging(capture_backend_log)
    app.run(host='0.0.0.0', port=5000, debug=True)