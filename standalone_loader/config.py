"""
Configuration for standalone policy loader.
"""
import os
from typing import List, Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Database - Use SQLite for simplicity in testing
    DATABASE_URL: str = "sqlite+aiosqlite:///policies.db"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)


settings = Settings()
