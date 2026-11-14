from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guild_id: int = Field(gt=0)
    channel_id: int = Field(gt=0)
    model: str = Field(min_length=1)
    database: Path
    knowledge: Path
    codex_bin: Path = Path("/opt/psa-support/bin/codex")
    codex_home: Path = Path("/var/lib/psa-support/codex-auth")
    daily_request_limit: int = Field(default=200, ge=1, le=10000)
    user_cooldown_seconds: int = Field(default=20, ge=1, le=3600)
    max_parallel_requests: int = Field(default=2, ge=1, le=4)

    @field_validator("model")
    @classmethod
    def real_model(cls, value):
        if value.startswith("REPLACE_"):
            raise ValueError("Set an available Codex model explicitly")
        return value

    @classmethod
    def load(cls, path: Path):
        config = cls.model_validate(json.loads(path.read_text()))
        for key in ("database", "knowledge"):
            value = getattr(config, key)
            if not value.is_absolute():
                setattr(config, key, (path.resolve().parent / value).resolve())
        return config

    def accepts(self, guild_id: int | None, channel_id: int, *, bot=False, webhook=False):
        # Exact IDs only: no DMs, other guilds, sibling channels, or child threads.
        return (not bot and not webhook and guild_id == self.guild_id
                and channel_id == self.channel_id)
