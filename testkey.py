import requests
import json

# Load the API key from config/config.json
def load_api_key():
    try:
        with open('config/config.json', 'r') as file:
            config = json.load(file)
            return config['OPENAI_API_KEY']
    except FileNotFoundError:
        print("config.json not found.")
        return None
    except KeyError:
        print("API key not found in config.json.")
        return None

# Get the API key
api_key = load_api_key()

if api_key:
    # Set the endpoint and headers for the API request
    url = "https://api.openai.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # Make the request to the API
    response = requests.get(url, headers=headers)

    # Check if the response status is OK (status code 200)
    if response.status_code == 200:
        print("API key is valid. Available models:")
        models = response.json()
        print(models)
    else:
        print(f"Error: {response.status_code}")
        print(response.json())  # Print the error message
else:
    print("No API key available. Please check config.json.")
