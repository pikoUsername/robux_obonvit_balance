from functools import lru_cache
from typing import List

from pydantic import BaseSettings


class Settings(BaseSettings):
    db_dsn: str
    db_type: str = "postgres"
    db_tokens_table: str
    db_bot_table: str

    window_size: str = "1920,1080"

    user_agent: str = "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
                      "AppleWebKit/537.36 (KHTML, like Gecko)" \
                      "Chrome/87.0.4280.141 Safari/537.36"

    debug: bool = True
    browser: str = "Chrome"
    browser_dsn: str = ""  # uses only when we are using remote browser

    loggers: List[str] = []

    class Config:
        validate_assignment = True
        env_file = "../.env"


@lru_cache
def get_settings():
    setting = Settings()
    return setting
