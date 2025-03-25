# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Agent configuration
MANAGER_MODEL = os.getenv("MODEL")
AGENT_MODEL = os.getenv("MODEL")

# Base URL
BASE_URL = os.getenv("BASE_URL")

# Web app configuration
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Cache configuration
CACHE_EXPIRY = 300  # seconds