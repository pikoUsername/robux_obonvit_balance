from app.settings import Settings
from app.repos import TokenRepository, BotRepository
from app.services.interfaces import BasicDBConnector


async def get_token_service(settings: Settings, connection: BasicDBConnector) -> TokenRepository:
	token_service = TokenRepository(connection, settings.db_tokens_table)

	await token_service.create_tokens_table()

	return token_service


async def get_bot_service(settings: Settings, connection: BasicDBConnector) -> BotRepository:
	bot_service = BotRepository(connection, settings.db_bot_table, settings.db_tokens_table)

	await bot_service.create_bots_table()

	return bot_service
