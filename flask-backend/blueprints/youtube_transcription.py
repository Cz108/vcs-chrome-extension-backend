import json
from flask import Blueprint, request, jsonify
import os
import requests
import yt_dlp
from pydub import AudioSegment
from langdetect import detect
from concurrent.futures import ThreadPoolExecutor, as_completed

youtube_transcription_bp = Blueprint('youtube_transcription', __name__)

# Path to temporarily store audio files
TEMP_AUDIO_PATH = "temp_audio"
if not os.path.exists(TEMP_AUDIO_PATH):
    os.makedirs(TEMP_AUDIO_PATH)

# Load the API key from config/config.json
def load_api_key():
    try:
        with open('config/config.json', 'r') as file:
            config = json.load(file)
            return config['OPENAI_API_KEY']
    except FileNotFoundError:
        print("config.json not found.")
        return None

# Function to download audio from YouTube
def download_audio_from_youtube(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{TEMP_AUDIO_PATH}/%(id)s.%(ext)s',  # Use the video ID instead of the title
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True  # This ensures that only one video is downloaded, not an entire playlist
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        audio_file_path = ydl.prepare_filename(info_dict)
        audio_file_path = os.path.splitext(audio_file_path)[0] + ".mp3"  # Ensure it's saved as MP3
        return audio_file_path

# Function to split the audio file into smaller chunks
def split_audio_file(audio_file_path, chunk_duration_ms=5*60*1000):  # 5 minutes per chunk
    audio = AudioSegment.from_mp3(audio_file_path)
    chunks = []
    
    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_name = f"{TEMP_AUDIO_PATH}/chunk_{i // chunk_duration_ms}.mp3"
        chunk.export(chunk_name, format="mp3")
        chunks.append(chunk_name)
    
    return chunks

# Function to transcribe an audio chunk using Whisper API
def transcribe_audio_chunk(audio_file_path, api_key):
    url_whisper = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    with open(audio_file_path, 'rb') as audio_file:
        files = {
            "file": (audio_file.name, audio_file, "audio/mpeg"),
            "model": (None, "whisper-1")
        }

        response = requests.post(url_whisper, headers=headers, files=files)
        
        if response.status_code != 200:
            raise Exception(f"Transcription failed: {response.text}")

        # Extract the transcription from the response
        transcription = response.json()['text']

        return transcription

# Function to detect the majority language of the transcription
def detect_language(text):
    try:
        return detect(text)  # Uses langdetect to detect the predominant language
    except Exception as e:
        print(f"Language detection failed: {e}")
        return "en"  # Default to English if detection fails

# Function to reword a chunk using ChatGPT
def reword_chunk(text_chunk, api_key, language):
    url_chatgpt = "https://api.openai.com/v1/chat/completions"
    headers_chatgpt = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant who is specialized in {language}."},
            {"role": "user", "content": f"Reword and summarize the following chunks in {language}:\n\n{text_chunk}"}
        ]
    }

    response = requests.post(url_chatgpt, headers=headers_chatgpt, json=payload)

    if response.status_code != 200:
        raise Exception(f"Summarization failed: {response.text}")

    summary = response.json()['choices'][0]['message']['content'].strip()
    return summary

# Function to summarize a chunk using ChatGPT
def summarize_chunk(text_chunk, api_key, language):
    url_chatgpt = "https://api.openai.com/v1/chat/completions"
    headers_chatgpt = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": f"You are a helpful assistant who summarizes in {language}."},
            {"role": "user", "content": f"Summarize the following video contents in {language}:\n\n{text_chunk}"}
        ],
        "max_tokens": 500
    }

    response = requests.post(url_chatgpt, headers=headers_chatgpt, json=payload)

    if response.status_code != 200:
        raise Exception(f"Summarization failed: {response.text}")

    summary = response.json()['choices'][0]['message']['content'].strip()
    return summary

# Parallel transcription and summarization for each chunk
def transcribe_and_summarize_chunk(chunk_path, api_key, detected_language):
    transcription = transcribe_audio_chunk(chunk_path, api_key)
    chunk_summary = summarize_chunk(transcription, api_key, detected_language)
    return transcription, chunk_summary

# Route to transcribe and summarize YouTube video audio
@youtube_transcription_bp.route('/transcribe_summarize_youtube', methods=['POST'])
def transcribe_summarize_youtube():
    audio_file_path = None
    try:
        data = request.json
        youtube_url = data.get('url', '')

        api_key = load_api_key()

        if api_key and youtube_url:
            # Step 1: Download audio from YouTube
            audio_file_path = download_audio_from_youtube(youtube_url)
            print(f"Audio downloaded at: {audio_file_path}")

            # Step 2: Split audio file into smaller chunks
            audio_chunks = split_audio_file(audio_file_path)
            print(f"Number of chunks: {len(audio_chunks)}")

            # Step 3: Transcribe and summarize each chunk using Whisper and ChatGPT in parallel
            full_transcription = ""
            chunk_summaries = []

            # Detect the language using the first chunk
            print(f"Transcribing first chunk for language detection...")
            first_chunk_transcription = transcribe_audio_chunk(audio_chunks[0], api_key)
            detected_language = detect_language(first_chunk_transcription)
            print(f"Detected language: {detected_language}")

            # Use ThreadPoolExecutor to parallelize the transcription and summarization
            with ThreadPoolExecutor() as executor:
                future_tasks = {
                    executor.submit(transcribe_and_summarize_chunk, chunk_path, api_key, detected_language): chunk_path
                    for chunk_path in audio_chunks
                }

                for future in as_completed(future_tasks):
                    transcription, chunk_summary = future.result()
                    full_transcription += transcription + "\n"
                    chunk_summaries.append(chunk_summary)

            print(f"Chunk summaries: {chunk_summaries}")

            # Step 4: Summarize the combined chunk summaries using ChatGPT
            combined_chunk_summaries = " ".join(chunk_summaries)
            print(f"Combined chunk summaries: {combined_chunk_summaries}")

            final_summary = reword_chunk(combined_chunk_summaries, api_key, detected_language)
            print(f"Final summary: {final_summary}")

            # Step 5: Clean up the downloaded audio file and chunks
            if audio_file_path and os.path.exists(audio_file_path):
                os.remove(audio_file_path)
            for chunk in audio_chunks:
                if os.path.exists(chunk):
                    os.remove(chunk)

            # Return only the final summary as a JSON object
            return jsonify(final_summary)
        else:
            return jsonify({"error": "Invalid request. No URL or API key provided."}), 400

    except Exception as e:
        print(f"Error occurred: {e}")
        # Clean up audio file even in case of error
        if audio_file_path and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return jsonify({"error": "An error occurred during the process.", "details": str(e)}), 400
