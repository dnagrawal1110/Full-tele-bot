import requests
import time
import logging
import os  # Add this import statement
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_avatar_video(
    audio_path: str, 
    api_key: str, 
    avatar_id: str, 
    max_retries: int = 3, 
    poll_interval: int = 10
) -> str:
    """
    Generate an avatar video using the HeyGen API.

    Args:
        audio_path (str): Path to the audio file to use for the video.
        api_key (str): Your HeyGen API key.
        avatar_id (str): The ID of the avatar to use.
        max_retries (int): Maximum number of retries for polling the video status. Defaults to 3.
        poll_interval (int): Time interval (in seconds) between polling attempts. Defaults to 10.

    Returns:
        str: Path to the generated video file.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        ValueError: If the API key or avatar ID is missing.
        Exception: If any step in the process fails.
    """
    # Validate inputs
    if not os.path.exists(audio_path):  # Now this will work
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    if not api_key:
        raise ValueError("HeyGen API key is required.")
    
    if not avatar_id:
        raise ValueError("Avatar ID is required.")

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        # Step 1: Upload audio file
        logger.info("Uploading audio file to HeyGen...")
        with open(audio_path, 'rb') as f:
            audio_resp = requests.post(
                "https://api.heygen.com/v1/audio/upload",
                headers=headers,
                files={"audio": f}
            )
        
        if audio_resp.status_code != 200:
            error_message = f"Audio upload failed. Status code: {audio_resp.status_code}, Response: {audio_resp.text}"
            logger.error(error_message)
            raise Exception(error_message)

        audio_url = audio_resp.json()['data']['url']
        logger.info("Audio file uploaded successfully.")

        # Step 2: Request video generation
        payload = {
            "avatar_id": avatar_id,
            "script": {"type": "audio", "audio_url": audio_url},
            "test": False
        }

        logger.info("Requesting video generation...")
        vid_resp = requests.post("https://api.heygen.com/v1/video/generate", json=payload, headers=headers)
        
        if vid_resp.status_code != 200:
            error_message = f"Video generation request failed. Status code: {vid_resp.status_code}, Response: {vid_resp.text}"
            logger.error(error_message)
            raise Exception(error_message)

        video_id = vid_resp.json()["data"]["video_id"]
        logger.info(f"Video generation started. Video ID: {video_id}")

        # Step 3: Poll for video completion
        video_url = None
        retries = 0
        while not video_url and retries < max_retries:
            logger.info(f"Checking video status (Attempt {retries + 1}/{max_retries})...")
            status_resp = requests.get(f"https://api.heygen.com/v1/video/status?video_id={video_id}", headers=headers)
            
            if status_resp.status_code != 200:
                error_message = f"Failed to check video status. Status code: {status_resp.status_code}, Response: {status_resp.text}"
                logger.error(error_message)
                retries += 1
                time.sleep(poll_interval)  # Wait before retrying
                continue

            status_data = status_resp.json()["data"]
            if status_data["status"] == "completed":
                video_url = status_data["video_url"]
                logger.info("Video generation completed successfully.")
            elif status_data["status"] == "failed":
                error_message = "Video generation failed."
                logger.error(error_message)
                raise Exception(error_message)
            else:
                retries += 1
                time.sleep(poll_interval)  # Wait before retrying

        if not video_url:
            error_message = f"Video generation did not complete after {max_retries} retries."
            logger.error(error_message)
            raise Exception(error_message)

        # Step 4: Download the generated video
        logger.info("Downloading generated video...")
        vid_content = requests.get(video_url).content
        file_path = f"output_video_{int(time.time())}.mp4"  # Unique filename using timestamp
        with open(file_path, "wb") as f:
            f.write(vid_content)

        logger.info(f"Video saved to {file_path}")
        return file_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error occurred: {e}")
        raise Exception(f"Network error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        raise Exception(f"Unexpected error: {e}")