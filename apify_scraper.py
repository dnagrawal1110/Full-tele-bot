import logging
import openai
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackContext,
    CallbackQueryHandler, filters
)
from voice_gen import generate_voice
from video_gen import generate_avatar_video
from snscrape_scraper import scrape_twitter_content  # Using snscrape
from dotenv import load_dotenv
import tempfile

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
USER_STATES = {}

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("📝 Direct Script", callback_data='direct')],
        [InlineKeyboardButton("🐦 Twitter Handle", callback_data='twitter')],
        [InlineKeyboardButton("🎤 Voice Idea", callback_data='voice')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to VideoBot! Choose your input method:", reply_markup=reply_markup)

async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    input_type = query.data
    USER_STATES[query.from_user.id] = {'input_type': input_type}
    prompts = {
        'direct': "Send your full script text (1-2 paragraphs):",
        'twitter': "Send a Twitter handle (without @), e.g., 'elonmusk':",
        'voice': "Send a voice message explaining your reel idea:",
    }
    await query.edit_message_text(text=prompts[input_type])

async def process_content(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_state = USER_STATES.get(user_id, {})
    if not user_state:
        await update.message.reply_text("Please start with /start")
        return

    try:
        input_type = user_state['input_type']

        if input_type == 'twitter' and 'handle' not in user_state:
            handle = update.message.text.strip()
            USER_STATES[user_id]['handle'] = handle
            await update.message.reply_text(f"Got handle @{handle}\nNow send a keyword to search:")
            return

        if input_type == 'twitter' and 'handle' in user_state and 'keyword' not in user_state:
            keyword = update.message.text.strip()
            handle = user_state['handle']
            USER_STATES[user_id]['keyword'] = keyword
            await update.message.reply_text(f"Scraping tweets for @{handle} with keyword '{keyword}'...")
            tweets = scrape_twitter_content(handle, keyword)
            if not tweets:
                await update.message.reply_text("No tweets found.")
                USER_STATES.pop(user_id, None)
                return
            prompt = "\n".join(tweets[:5])
            script = generate_gpt_script(prompt)

        elif input_type == 'direct':
            script = update.message.text.strip()

        elif input_type == 'voice':
            if update.message.voice:
                voice_file = await update.message.voice.get_file()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_audio:
                    await voice_file.download_to_drive(temp_audio.name)
                    temp_path = temp_audio.name
                with open(temp_path, "rb") as audio_file:
                    transcript = openai.Audio.transcribe(model="whisper-1", file=audio_file)
                os.remove(temp_path)
                prompt = transcript["text"]
                await update.message.reply_text(f"Transcribed Idea:\n{prompt}")
                script = generate_gpt_script(prompt)
            else:
                await update.message.reply_text("Send a voice message.")
                return

        await update.message.reply_text(f"Generated Script:\n\n{script}")
        await update.message.reply_text("Generating voiceover...")
        audio_file = generate_voice(text=script, eleven_api_key=os.getenv('ELEVEN_LABS_API_KEY'))
        await update.message.reply_text("Creating avatar video...")
        video_file = generate_avatar_video(audio_path=audio_file, api_key=os.getenv('HEYGEN_API_KEY'), avatar_id=os.getenv('AVATAR_ID'))

        with open(video_file, 'rb') as vid:
            await update.message.reply_video(video=vid, caption="Your Custom Video", supports_streaming=True)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await update.message.reply_text(f"Error occurred: {e}")

    finally:
        USER_STATES.pop(user_id, None)
        if 'audio_file' in locals() and os.path.exists(audio_file):
            os.remove(audio_file)
        if 'video_file' in locals() and os.path.exists(video_file):
            os.remove(video_file)

def generate_gpt_script(prompt: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"Create a 60-second video script using this input:\n{prompt}\n\nRequirements:\n1. Conversational, easy-to-understand language.\n2. Natural pauses for voiceover.\n3. Include scene descriptions in [brackets].\n4. Max 300 words."
        }]
    )
    return response.choices[0].message.content.strip()

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_content))
    app.add_handler(MessageHandler(filters.VOICE, process_content))
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()