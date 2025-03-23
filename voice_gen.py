import requests
import os
import uuid
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_voice(
    text: str, 
    eleven_api_key: str, 
    voice_id: Optional[str] = "21m00Tcm4TlvDq8ikWAM"  # Replace with a valid voice_id
) -> str:
    """
    Generate speech from text using ElevenLabs API.
    
    Args:
        text (str): The text to convert to speech.
        eleven_api_key (str): Your ElevenLabs API key.
        voice_id (str, optional): The ID of the voice to use. Defaults to a valid voice_id.
    
    Returns:
        str: The path to the saved audio file.
    
    Raises:
        ValueError: If the text or API key is empty.
        Exception: If the API request fails or if there is a network error.
    """
    # Validate input
    if not text.strip():
        raise ValueError("Text cannot be empty.")
    
    if not eleven_api_key:
        raise ValueError("ElevenLabs API key is required.")
    
    # API endpoint and headers
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": eleven_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }

    # Payload for the API request
    payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }

    try:
        # Make the API request
        logger.info("Sending request to ElevenLabs API...")
        response = requests.post(url, headers=headers, json=payload)

        # Check for errors in the response
        if response.status_code != 200:
            error_message = f"Voice generation failed. Status code: {response.status_code}, Response: {response.text}"
            logger.error(error_message)
            raise Exception(error_message)

        # Save the audio to a temporary file
        audio_path = f"output_{uuid.uuid4().hex}.mp3"
        with open(audio_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"Audio successfully saved to {audio_path}")
        return audio_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error occurred: {e}")
        raise Exception(f"Network error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        raise Exception(f"Unexpected error: {e}")