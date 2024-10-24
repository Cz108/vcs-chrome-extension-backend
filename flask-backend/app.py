from flask import Flask
from flask_cors import CORS

# Import blueprints
from blueprints.summarization import summarization_bp
from blueprints.transcription import transcription_bp
from blueprints.youtube_transcription import youtube_transcription_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(summarization_bp)
app.register_blueprint(transcription_bp)
app.register_blueprint(youtube_transcription_bp)

if __name__ == "__main__":
    app.run(debug=True)
