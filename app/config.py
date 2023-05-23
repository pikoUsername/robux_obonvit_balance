from functools import lru_cache
from typing import List

from pydantic import BaseSettings, SecretStr

from app.consts import DEFAULT_QUEUE_NAME, EXHANGE_DEFAULT_NAME


class Settings(BaseSettings):
    db_dsn: str
    db_tokens_table: str
    queue_dsn: str

    window_size: str = "1920,1080"

    queue_name: str = DEFAULT_QUEUE_NAME
    exchange_name: str = EXHANGE_DEFAULT_NAME

    user_agent: str = "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
                      "AppleWebKit/537.36 (KHTML, like Gecko)" \
                      "Chrome/87.0.4280.141 Safari/537.36"

    debug: bool = True
    browser: str = "Chrome"

    loggers: List[str] = []

    class Config:
        validate_assignment = True
        env_file = "../.env"


@lru_cache
def get_settings():
    setting = Settings()
    return setting
