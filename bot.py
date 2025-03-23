import logging
import openai
import os
import tempfile
import asyncio
import nest_asyncio
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackContext,
    CallbackQueryHandler, filters
)
from voice_gen import generate_voice
from video_gen import generate_avatar_video
from dotenv import load_dotenv

# Apply nest_asyncio for Jupyter notebook compatibility
nest_asyncio.apply()

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User state tracking
USER_STATES: Dict[int, Dict[str, Any]] = {}

async def start(update: Update, context: CallbackContext) -> None:
    """
    Handle the /start command. Display a menu for the user to choose an input method.
    """
    keyboard = [
        [InlineKeyboardButton("📝 Direct Script", callback_data='direct')],
        [InlineKeyboardButton("🐦 Twitter Handle", callback_data='twitter')],
        [InlineKeyboardButton("🎤 Voice Idea", callback_data='voice')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎥 Welcome to VideoBot! Choose your input method:", reply_markup=reply_markup)

async def handle_button(update: Update, context: CallbackContext) -> None:
    """
    Handle button presses from the user.
    """
    query = update.callback_query
    await query.answer()
    input_type = query.data
    USER_STATES[query.from_user.id] = {'input_type': input_type}
    prompts = {
        'direct': "✍️ Send your full script text (1-2 paragraphs):",
        'twitter': "🔗 Send a Twitter handle (without @), e.g., 'elonmusk':",
        'voice': "🎤 Send a voice message explaining your reel idea:",
    }
    await query.edit_message_text(text=prompts[input_type])

async def process_content(update: Update, context: CallbackContext) -> None:
    """
    Process user input based on their selected input method.
    """
    user_id = update.message.from_user.id
    user_state = USER_STATES.get(user_id)

    if user_state is None:
        await update.message.reply_text("⚠️ Please start with /start")
        return

    try:
        input_type = user_state['input_type']

        if input_type == 'direct':
            script = update.message.text.strip()
            await update.message.reply_text("📝 Processing your script...")

        elif input_type == 'voice':
            if update.message.voice:
                await update.message.reply_text("🎤 Transcribing your voice message...")
                voice_file = await update.message.voice.get_file()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_audio:
                    await voice_file.download_to_drive(temp_audio.name)
                    temp_path = temp_audio.name
                with open(temp_path, "rb") as audio_file:
                    transcript = openai.Audio.transcribe(model="whisper-1", file=audio_file)
                os.remove(temp_path)
                prompt = transcript["text"]
                await update.message.reply_text(f"🖋️ Transcribed Idea:\n{prompt}")
                await update.message.reply_text("📝 Generating script from your idea...")
                script = generate_gpt_script(prompt)
            else:
                await update.message.reply_text("⚠️ Please send a voice message.")
                return

        elif input_type == 'twitter':
            await update.message.reply_text("⚠️ Twitter scraping is currently paused. Use /start to choose another option.")
            return

        # Send the generated script to the user
        await update.message.reply_text(f"📄 Generated Script:\n\n{script}")

        # Generate voiceover
        await update.message.reply_text("🔊 Generating voiceover...")
        audio_file_path = generate_voice(text=script, eleven_api_key=os.getenv('ELEVEN_LABS_API_KEY'))

        # Send the voiceover to the user
        with open(audio_file_path, 'rb') as audio:
            await update.message.reply_audio(audio=audio, caption="🎧 Your Voiceover File")

        # Generate avatar video
        await update.message.reply_text("🎬 Creating avatar video...")
        video_file_path = generate_avatar_video(
            audio_path=audio_file_path,
            api_key=os.getenv('HEYGEN_API_KEY'),
            avatar_id=os.getenv('AVATAR_ID')
        )

        # Send the video to the user
        with open(video_file_path, 'rb') as vid:
            await update.message.reply_video(video=vid, caption="🎥 Your Custom Video", supports_streaming=True)

    except Exception as e:
        logger.error(f"Error processing content: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ An error occurred: {e}")

    finally:
        # Clean up user state and temporary files
        USER_STATES.pop(user_id, None)
        if 'audio_file_path' in locals() and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        if 'video_file_path' in locals() and os.path.exists(video_file_path):
            os.remove(video_file_path)

def generate_gpt_script(prompt: str) -> str:
    """
    Generate a script using OpenAI's GPT-4 model.
    
    Args:
        prompt (str): The input prompt for the script.
    
    Returns:
        str: The generated script.
    """
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"Create a 60-second video script using this input:\n{prompt}\n\nRequirements:\n1. Conversational, easy-to-understand language.\n2. Natural pauses for voiceover.\n3. Include scene descriptions in [brackets].\n4. Max 300 words."
        }]
    )
    return response.choices[0].message.content.strip()

async def run_bot() -> None:
    """
    Start the Telegram bot and set up handlers.
    """
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_content))
    app.add_handler(MessageHandler(filters.VOICE, process_content))
    logger.info("[BOT STATUS] Bot is running...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(run_bot())