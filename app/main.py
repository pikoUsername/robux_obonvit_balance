import time

from aiohttp import ClientSession
from dotenv import load_dotenv
from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from app.browser import auth_browser
from app.consts import INTERVAL
from app.providers import get_token_service, get_bot_service
from app.schemas import BotScheme
from app.services.db import get_db_conn
from app.services.driver import get_driver, convert_browser_cookies_to_aiohttp, presence_of_any_text_in_element
from app.log import configure_logging
from app.settings import get_settings

import nest_asyncio

nest_asyncio.apply()


async def main():
    load_dotenv()

    settings = get_settings()

    configure_logging(settings.loggers)
    connection = await get_db_conn(settings.db_dsn)
    token_service = await get_token_service(settings, connection)
    bot_service = await get_bot_service(settings, connection)
    driver = get_driver(settings)

    token = await auth_browser(driver, token_service)

    cookies = convert_browser_cookies_to_aiohttp(driver.get_cookies())
    session = ClientSession(cookies=cookies)
    last_update_time = time.time()

    logger.info("Starting application")

    try:
        while True:
            if time.time() < last_update_time + INTERVAL:
                continue

            amount = WebDriverWait(driver, 3).until(
                presence_of_any_text_in_element((By.ID, "nav-robux-amount"))
            )
            nickname = driver.find_element(By.CSS_SELECTOR, ".age-bracket-label-username")

            logger.info("Fetching tokens")
            result = await bot_service.fetch_bot_by_token(token=token)
            if not result:
                bot = BotScheme(
                    balance=int(amount.text),
                    token=token,
                    active=True,
                    nickname=nickname.text,
                )

                await bot_service.add_bot(bot)
                result = bot
            if result.balance != int(amount.text):
                await bot_service.update_balance_by_token(token, int(amount.text))
            last_update_time = time.time()
            driver.refresh()
    except:
        raise
    finally:
        driver.close()
        await connection.close()
        await session.close()
