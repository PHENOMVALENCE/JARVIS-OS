"""Local configuration loaded from an untracked .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

# This is a place for directories and non-secret settings.
# While you don't have to keep all of your directories in this file, 
# I have found that it is much easier to just have them all in one place


############ - Directories - #############
system_call_file = '.\\caches and calls\\System_Call.txt'
mic_beep = ".\\sounds\\beep-24.mp3"
mute_beep = ".\\sounds\\mute.mp3"
mic_png = ".\\GUI_images\\mic.png"
background_png = ".\\GUI_images\\background.png"
GUI_mic_png = ".\\GUI_images\\GUI_mic.png"
GUI_image_dir = ".\\GUI_images"
image_search_root_dir = ".\\images"
log_files_root_dir = ".\\J.A.R.V.I.S log files"
vision_image = ".\\GUI_images\\Vision.jpg"
jarvis_text_image = ".\\GUI_images\\JARVIS_TEXT.png"
user_text_image = ".\\GUI_images\\USER_TEXT.png"
hacker_image = ".\\GUI_images\\Hacker.png"
font_file = ".\\GUI_images\\Squares Bold Free.otf"
loading_image = ".\\GUI_images\\loading.jpg"
client = ".\\caches and calls\\client.json"
token = ".\\caches and calls\\token.json"
###########################################

############ - SMS info - #############
phone_number = os.getenv("JARVIS_PHONE_NUMBER", "")
phone_provider = os.getenv("JARVIS_PHONE_PROVIDER", "")
sender_email = os.getenv("JARVIS_SENDER_EMAIL", "")
sender_provider_password = os.getenv("JARVIS_SENDER_PASSWORD", "")
#######################################

############ - API keys - #############
porcupine_API_key = os.getenv("PORCUPINE_API_KEY", "")
google_search_API_key = os.getenv("SERPAPI_API_KEY", "")
OpenAI_API_key = os.getenv("OPENAI_API_KEY", "")
OpenAI_assistant_ID = os.getenv("OPENAI_ASSISTANT_ID", "")
OpenAI_thread_ID = os.getenv("OPENAI_THREAD_ID", "")
eleven_labs_API_key = os.getenv("ELEVENLABS_API_KEY", "")
#######################################

#Video for google cloud gmail api installation here: https://www.youtube.com/watch?v=7E3NNxeXiys watch up to 9 min mark, code is take care of
#IMPORTANT: Rename the client file you recieve to exactly "client.json" and place it in the "caches and calls" directory for everything to work correctly

############ - Spotify info - #############
client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
###########################################

llm_provider = os.getenv("JARVIS_LLM_PROVIDER", "ollama").lower()
ollama_model = os.getenv("OLLAMA_MODEL", "gemma2:2b")
enable_hand_volume = env_bool("JARVIS_ENABLE_HAND_VOLUME", False)
