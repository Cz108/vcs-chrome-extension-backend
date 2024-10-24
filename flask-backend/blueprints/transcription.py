from flask import Blueprint, request, jsonify
import requests
import json

transcription_bp = Blueprint('transcription', __name__)

# Load the API key from config/config.json
def load_api_key():
    try:
        with open('config/config.json', 'r') as file:
            config = json.load(file)
            return config['OPENAI_API_KEY']
    except FileNotFoundError:
        print("config.json not found.")
        return None

@transcription_bp.route('/transcribe', methods=['POST'])
def transcribe_audio():
    api_key = load_api_key()
    
    if api_key:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({"error": "No audio file provided."}), 400
        
        files = {
            "file": (audio_file.filename, audio_file.stream, "audio/mpeg"),
            "model": (None, "whisper-1")
        }
        
        response = requests.post(url, headers=headers, files=files)
        
        if response.status_code == 200:
            result = response.json()
            return jsonify(result['text'].strip())
        else:
            return jsonify({"error": "API request failed", "status_code": response.status_code}), 400
    else:
        return jsonify({"error": "Invalid API key."}), 400
