from flask import Blueprint, request, jsonify
import requests
import json

summarization_bp = Blueprint('summarization', __name__)

# Load the API key from config/config.json
def load_api_key():
    try:
        with open('config/config.json', 'r') as file:
            config = json.load(file)
            return config['OPENAI_API_KEY']
    except FileNotFoundError:
        print("config.json not found.")
        return None

@summarization_bp.route('/summarize', methods=['POST'])
def summarize_text():
    try:
        data = request.json
        user_input = data.get('text', '')

        api_key = load_api_key()

        if api_key and user_input:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Summarize the following text:\n\n{user_input}"}
                ],
                "max_tokens": 150
            }

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                return jsonify(result['choices'][0]['message']['content'].strip())
            else:
                return jsonify({"error": "API request failed", "status_code": response.status_code, "details": response.text}), 400
        else:
            return jsonify({"error": "Invalid request. No text or API key provided."}), 400
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "Invalid request format."}), 400
