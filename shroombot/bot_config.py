"""
Configuration system for multi-bot support
"""

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class BotType(str, Enum):
    """Type of bot behavior"""

    FORUM = "forum"  # Topic-based with forum threads
    SIMPLE = "simple"  # Reply-based without topics


@dataclass
class BotConfig:
    """Configuration for a single bot instance"""

    bot_id: str  # Unique identifier (e.g., "bot1", "bot2")
    bot_type: BotType
    bot_token: str
    api_id: int
    api_hash: str
    admin_chat_id: int

    # Per-bot resources
    ban_file: str
    mapping_file: str
    encryption_key: str  # Base64 encoded

    # Bot-specific behavior
    name_type: Literal["mushroom", "generic"]

    # Optional: Bot-specific files directory
    files_dir: str | None = None


@dataclass
class SharedConfig:
    """Shared configuration across all bots"""

    bind: str  # Server bind address (e.g., "0.0.0.0:8000")
    root_path: str = ""  # API root path


@dataclass
class MultiBotConfig:
    """Complete configuration for multi-bot deployment"""

    shared: SharedConfig
    bots: list[BotConfig]

    @classmethod
    def from_json_file(cls, file_path: str) -> "MultiBotConfig":
        """
        Load configuration from JSON file with environment variable substitution

        Supports ${VAR_NAME} syntax for environment variables in the JSON file
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Substitute environment variables
        content = cls._substitute_env_vars(content)

        data = json.loads(content)

        shared = SharedConfig(**data["shared"])

        # Convert bot_type strings to enum
        bots = []
        for bot_data in data["bots"]:
            bot_type_str = bot_data.pop("bot_type")
            bot_type = BotType(bot_type_str)
            bots.append(BotConfig(bot_type=bot_type, **bot_data))

        return cls(shared=shared, bots=bots)

    @staticmethod
    def _substitute_env_vars(content: str) -> str:
        """
        Substitute ${VAR_NAME} with environment variable values

        Raises ValueError if a required environment variable is not set
        """

        def replacer(match: re.Match):
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(
                    f"Environment variable {var_name} is not set but required in config"
                )
            return value

        return re.sub(r"\$\{([^}]+)\}", replacer, content)
