import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower().strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def validate_config():
    missing = []
    if not DISCORD_TOKEN:
        missing.append("DISCORD_TOKEN")
    
    if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY (or switch AI_PROVIDER=openai and supply OPENAI_API_KEY)")
    elif AI_PROVIDER == "openai" and not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY (or switch AI_PROVIDER=gemini and supply GEMINI_API_KEY)")
        
    return missing
