from typing import Sequence, Union, Optional

from loguru import logger

from app.schemas import BotScheme
from app.services.interfaces import BasicDBConnector


class TokenRepository:
    def __init__(self, conn: BasicDBConnector, model_name: str) -> None:
        self.conn = conn

        self._model_name = model_name

    async def fetch_active_tokens(self, limit: int = 10) -> Union[Sequence[str], str]:
        conn = self.conn
        model_name = self._model_name

        sql = f"SELECT token FROM {model_name} WHERE is_active = true LIMIT {limit}"

        results: Sequence[dict] = await conn.fetchmany(sql)
        tokens = []
        for record in results:
            tokens.append(record.get("token"))
        return tokens

    async def fetch_token(self) -> Optional[str]:
        """
        Выбирает рандомный свободный токен

        :return:
        """
        tokens = await self.fetch_active_tokens()
        if not tokens:
            return ""
        return tokens[0]

    async def mark_as_inactive(self, token: str) -> None:
        conn = self.conn
        model_name = self._model_name

        await conn.execute(f"UPDATE {model_name} SET is_active = false WHERE token = $1", token)

    async def create_tokens_table(self) -> None:
        conn = self.conn
        model_name = self._model_name

        await conn.execute(f"CREATE TABLE IF NOT EXISTS {model_name} ("
                           f"token TEXT PRIMARY KEY, is_active BOOLEAN DEFAULT true);")


class BotRepository:
    def __init__(self, conn: BasicDBConnector, model_name: str, token_model_name: str):
        self.conn = conn
        self.model_name = model_name
        self.token_model_name = token_model_name

    async def fetch_bot_by_token(self, token: str) -> Optional[BotScheme]:
        sql = f"SELECT * FROM {self.model_name} WHERE token = $1 LIMIT 1"
        result = await self.conn.fetch(sql, token)
        if result:
            return BotScheme(**result)
        return None

    async def fetch_bot_by_id(self, id: int) -> Optional[BotScheme]:
        sql = f"SELECT * FROM {self.model_name} WHERE id = $1 LIMIT 1"
        result = await self.conn.fetch(sql, id)
        if result:
            return BotScheme(**result)
        return None

    async def mark_as_inactive(self, id: int) -> None:
        sql = f"UPDATE {self.model_name} SET active = false WHERE id = $1"
        await self.conn.execute(sql, id)

    async def add_bot(self, bot: BotScheme) -> None:
        sql = f"INSERT INTO {self.model_name} (balance, token, active, nickname) VALUES ($1, $2, $3, $4)"
        await self.conn.execute(sql, bot.balance, bot.token, bot.active, bot.nickname)

    async def update_balance_by_token(self, token: str, new_balance: int) -> None:
        sql = f"UPDATE {self.model_name} SET balance = $1 WHERE token = $2"
        await self.conn.execute(sql, new_balance, token)

    async def update_balance_by_id(self, id: int, new_balance: int) -> None:
        sql = f"UPDATE {self.model_name} SET balance = $1 WHERE id = $2"
        await self.conn.execute(sql, new_balance, id)

    async def create_bots_table(self) -> None:
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.model_name} (
            id SERIAL PRIMARY KEY,
            balance INT NOT NULL,
            token TEXT UNIQUE NOT NULL REFERENCES {self.token_model_name},
            active BOOLEAN DEFAULT true,
            nickname TEXT
        );
        """
        await self.conn.execute(sql)
