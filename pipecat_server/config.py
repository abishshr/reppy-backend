"""Configuration for Pipecat AI Coach server."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DailyConfig:
    """Daily.co WebRTC configuration."""
    api_key: str
    domain: str

    @classmethod
    def from_env(cls) -> "DailyConfig":
        return cls(
            api_key=os.getenv("DAILY_API_KEY", ""),
            domain=os.getenv("DAILY_DOMAIN", "cloud-18b9eea0517e4bd496b3a482f6cfc8a0"),
        )

    @property
    def api_url(self) -> str:
        return f"https://api.daily.co/v1"


@dataclass
class GeminiConfig:
    """Gemini Live API configuration."""
    api_key: str
    model: str
    voice_id: str

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        return cls(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
            voice_id=os.getenv("GEMINI_VOICE_ID", "Puck"),
        )


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str
    port: int
    debug: bool

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            host=os.getenv("PIPECAT_HOST", "0.0.0.0"),
            port=int(os.getenv("PIPECAT_PORT", "7860")),
            debug=os.getenv("PIPECAT_DEBUG", "false").lower() == "true",
        )


@dataclass
class Config:
    """Main configuration container."""
    daily: DailyConfig
    gemini: GeminiConfig
    server: ServerConfig

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            daily=DailyConfig.from_env(),
            gemini=GeminiConfig.from_env(),
            server=ServerConfig.from_env(),
        )


# Global config instance
config = Config.from_env()
