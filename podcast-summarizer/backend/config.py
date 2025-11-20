"""
Configuration module for the podcast summarizer application.
Loads environment variables and stores application settings.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings and configuration."""
    
    # Base Directory
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")  # Get free key at newsapi.org
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")  # Get free key at tavily.com
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")  # Get key at perplexity.ai
    EXA_API_KEY: str = os.getenv("EXA_API_KEY", "")  # Get key at exa.ai
    
    # Gmail API
    GMAIL_ENABLED: bool = os.getenv("GMAIL_ENABLED", "False").lower() == "true"
    
    # Application Settings
    APP_NAME: str = "Podcast Summarizer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS Settings
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # RSS Feed Settings
    MAX_EPISODES_PER_FEED: int = 5
    REQUEST_TIMEOUT: int = 30  # seconds
    
    # Test Mode Settings
    TEST_MODE: bool = os.getenv("TEST_MODE", "False").lower() == "true"
    TEST_TRANSCRIPT_LENGTH: int = int(os.getenv("TEST_TRANSCRIPT_LENGTH", "5000"))  # chars for quick testing
    
    # YouTube Settings
    YOUTUBE_COOKIES_PATH: str = os.getenv("YOUTUBE_COOKIES_PATH", "")  # Optional: path to YouTube cookies for bypassing IP blocks
    
    # Email Settings (for sending briefings)
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "")  # Gmail address to send from
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")  # Gmail app password (not regular password!)
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")  # Email to send briefings to
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate that required settings are present.
        
        Returns:
            bool: True if all required settings are valid
        """
        if not cls.OPENAI_API_KEY:
            print("Warning: OPENAI_API_KEY not set in environment variables")
            return False
        return True


settings = Settings()

