import asyncio
import json
import time
from typing import Optional

import pydantic
from aiohttp import ClientSession
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.config import Settings
from app.services.abc import IListener, BasicDBConnector
from app.services.db import get_db_conn
from app.services.driver import set_token, convert_browser_cookies_to_aiohttp, get_driver, \
    presence_of_any_text_in_element
from app.repos import TokenService
from app.consts import ROBLOX_TOKEN_KEY, TOKEN_RECURSIVE_CHECK, ROBLOX_HOME_URL
from app.services.exceptions import SkipException, CancelException
from app.services.helpers import validate_url
from app.services.publisher import BasicMessageSender
from app.schemas import ReturnSignal, StatusCodes
from app.schemas import PurchaseData


def auth(browser: Chrome, token: str):
    """
    Just sets a token and refreshes the page

    :param browser:
    :param token:
    :return:
    """
    browser.get(ROBLOX_HOME_URL)
    set_token(browser, token)  # noqa
    browser.refresh()


def press_agreement_button(browser: Chrome):
    try:
        logger.info("Pressing user agreement button")
        btn = browser.find_element(By.CSS_SELECTOR, ".modal-window .modal-footer .modal-button")
        btn.click()
    except NoSuchElementException:
        return


class UrlHandler(IListener):
    """
    Основной хендлер всех запросов,

    Он должен иметь в __init__ только самое необходимое!

    Очень грязный код
    """
    def __init__(self) -> None:
        self.config: Optional[Settings] = None

        self.token_service: Optional[TokenService] = None
        self.setupped = False

    async def setup(self, data: dict, conn: BasicDBConnector, settings: Settings, token_service: TokenService):
        driver = get_driver(settings)

        logger.info("Driver has been set")

        loop = asyncio.get_event_loop()

        _task = loop.create_task(token_service.fetch_token())
        token = loop.run_until_complete(_task)
        if not token:
            raise ValueError("No tokens available")

        logger.info("First token has been taken")

        cookies = convert_browser_cookies_to_aiohttp(driver.get_cookies())

        session = ClientSession(cookies=cookies)

        logger.info("Logging in")
        auth(driver, token)
        logger.info("Login complete")

        self.setupped = True

        data.update(driver=driver, session=session)

    def close(self, driver: Chrome, session):
        driver.quit()

        loop = asyncio.get_event_loop()

        loop.run_until_complete(session.close())

        logger.info("Closing up...")

    def get_robuxes(self, driver: Chrome) -> int:
        text = WebDriverWait(driver, 5).until(
            presence_of_any_text_in_element((By.ID, "nav-robux-amount"))
        )
        return int(text)

    async def mark_as_spent(self, driver) -> None:
        token = driver.get_cookie(ROBLOX_TOKEN_KEY)
        await self.token_service.mark_as_spent(token)

    async def change_token(self, driver) -> None:
        # marks the current token as spent
        await self.mark_as_spent(driver)
        driver.delete_cookie(name=ROBLOX_TOKEN_KEY)
        token = await self.token_service.fetch_token()
        if not token:
            logger.info("OUT OF TOKENS")
            return
        set_token(driver, token)
        driver.refresh()

    async def change_token_recursive(self, driver: Chrome, depth: int = TOKEN_RECURSIVE_CHECK):
        if depth == 0:
            raise RuntimeError("TOKENS CORRUPTED, WAITING FOR ACTIONS")
        await self.change_token(driver)
        if not self.check_page_for_valid_login(driver):
            await self.change_token(driver)
        await self.change_token_recursive(driver, depth - 1)

    def check_page_for_valid_login(self, driver: Chrome) -> bool:
        # finds a signup button, if yes, then it returns False
        try:
            driver.find_element(By.CLASS_NAME, "rbx-navbar-signup")
        except NoSuchElementException:
            return True
        return False

    async def __call__(
            self,
            driver: Chrome,
            purchase_data: PurchaseData,
            settings: Settings,
            publisher: BasicMessageSender,
            data: dict
    ) -> None:
        logger.info(f"Redirecting to {purchase_data.url}")
        driver.get(purchase_data.url)
        robux = self.get_robuxes(driver)
        if purchase_data != robux:
            logger.info("Price is not equal to url's price")

            data.update(
                return_signal=ReturnSignal(status_code=StatusCodes.invalid_price)
            )

            return
        if settings.debug:
            driver.save_screenshot("screenshot.png")
        cost = driver.find_element(By.CLASS_NAME, "text-robux-lg")
        if robux < 5 or int(cost.text) > robux:
            try:
                await self.change_token_recursive(driver)
            except RuntimeError:
                data.update(
                    return_signal=ReturnSignal(
                        status_code=StatusCodes.no_tokens_available,
                    )
                )
                return
        press_agreement_button(driver)
        try:
            btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")
            btn.click()
        except NoSuchElementException:
            logger.info("Gamepass has been already bought")
            _temp = ReturnSignal(
                status_code=StatusCodes.already_bought,
            )
            logger.debug("Sending back information about.")
        else:
            confirm_btn = driver.find_element(By.CSS_SELECTOR, "a#confirm-btn.btn-primary-md")
            logger.info("Clicking buy now")
            # HERE IT BUYS GAMEPASS
            confirm_btn.click()
            logger.info(f"Purchased gamepass for {cost.text} robuxes")
            _temp = ReturnSignal(
                status_code=StatusCodes.success,
            )
        data.update(return_signal=_temp)


class DBHandler(IListener):
    async def setup(self, data: dict, settings: Settings):
        logger.info("Creating database connection...")
        conn = await get_db_conn(settings)
        logger.info("Database conn complete")

        token_service = TokenService.get_current(
            no_error=True
        ) or TokenService(conn, settings.db_tokens_table)

        await token_service.create_tokens_table()

        data.update(token_service=token_service, conn=conn)

    async def close(self, conn: BasicDBConnector):
        await conn.close()

    def __call__(self, *args, **kwargs):
        pass


class PublisherHandler(IListener):
    async def setup(self, data: dict, settings: Settings) -> None:
        logger.info("Setting up basicMessageSender")

        publisher = BasicMessageSender(
            settings.queue_dsn,
            queue=settings.send_queue_name,
            exchange=settings.send_queue_exchange_name,
            routing=settings.send_queue_name,
        )
        publisher.connect()
        logger.info("Connection to publisher has been established")

        data.update(publisher=publisher)

    def close(self, publisher: BasicMessageSender):
        publisher.close()

    def __call__(self, *args, **kwargs):
        pass


class ErrorHandler(IListener):
    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def __call__(self, err: Exception):
        logger.exception(err)


class DataHandler(IListener):
    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def __call__(self, data: dict, body: bytes, publisher: BasicMessageSender):
        try:
            _temp = json.loads(body)
            pur_data = PurchaseData(**_temp)
        except json.JSONDecodeError:
            logger.error("NOT HELLO")

            raise CancelException
        except pydantic.ValidationError as e:
            logger.info(f"Invalid data: {body}")

            data = ReturnSignal(status_code=StatusCodes.invalid_data, errors=[e.errors()])

            publisher.send_message(data.dict())
            raise CancelException

        data.update(purchase_data=pur_data)


class ReturnSignalHandler(IListener):
    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def __call__(self, publisher: BasicMessageSender, return_signal: ReturnSignal = None, ):
        if return_signal is not None:
            publisher.send_message(return_signal.dict())
