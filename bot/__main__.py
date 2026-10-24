import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from .ai import WasteAnalyzer
from .config import Config, load_config
from .db import Database
from .handlers import router
from .keyboards import set_webapp_url
from .texts import COMMANDS, DEFAULT_LANG, DESCRIPTION, SHORT_DESCRIPTION, t
from .web import create_web_app

log = logging.getLogger("taza_men")


async def setup_bot_profile(bot: Bot, config: Config) -> None:
    """Команды, описание и кнопка Mini App на обоих языках (язык по умолчанию — для всех остальных)."""
    for lang, commands in COMMANDS.items():
        language_code = None if lang == DEFAULT_LANG else lang
        try:
            await bot.set_my_commands(
                [BotCommand(command=name, description=desc) for name, desc in commands],
                language_code=language_code,
            )
            await bot.set_my_description(DESCRIPTION[lang], language_code=language_code)
            await bot.set_my_short_description(SHORT_DESCRIPTION[lang], language_code=language_code)
        except Exception:
            log.warning("Не удалось обновить профиль бота для языка %s", lang, exc_info=True)

    try:
        if config.webapp_url:
            button = MenuButtonWebApp(
                text=t("menu_button", DEFAULT_LANG), web_app=WebAppInfo(url=f"{config.webapp_url}/")
            )
        else:
            button = MenuButtonCommands()
        await bot.set_chat_menu_button(menu_button=button)
    except Exception:
        log.warning("Не удалось установить кнопку меню", exc_info=True)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    config = load_config()
    set_webapp_url(config.webapp_url)

    db = Database(config.db_path)
    await db.connect()

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["config"] = config
    dp["analyzer"] = WasteAnalyzer(config.gemini_api_key, config.gemini_models)
    dp.include_router(router)

    app = create_web_app(config, db, bot)
    if config.use_webhook:
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=config.webhook_secret).register(
            app, path=config.webhook_path
        )
        setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, config.web_host, config.web_port).start()
    log.info("Mini App сервер: http://%s:%s (публичный адрес: %s)", config.web_host, config.web_port,
             config.webapp_url or "не задан — кнопки карты скрыты")

    await setup_bot_profile(bot, config)
    me = await bot.get_me()
    log.info("Taza Men запущен: @%s, режим %s, модели %s, демо-режим: %s", me.username,
             "webhook" if config.use_webhook else "polling", ", ".join(config.gemini_models), config.demo_mode)

    try:
        if config.use_webhook:
            # drop_pending_updates=False: не теряем сообщения, пришедшие во время деплоя или сна сервиса
            await bot.set_webhook(
                f"{config.webapp_url}{config.webhook_path}",
                secret_token=config.webhook_secret,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            await wait_for_shutdown()
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await db.close()
        await bot.session.close()


async def wait_for_shutdown() -> None:
    """В режиме вебхука просто держим сервер, пока хостинг не попросит остановиться."""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: остановка по Ctrl+C через KeyboardInterrupt
    await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())
