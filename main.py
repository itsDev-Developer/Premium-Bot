import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

import config
import db
import services
from api import create_app
from handlers import admin, buy, payments, user
from middleware import UserMW


async def main():
    logging.basicConfig(level=logging.INFO)
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS is empty - admin commands will not work!")
    await db.init()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.message.outer_middleware(UserMW())
    dp.callback_query.outer_middleware(UserMW())
    dp.include_routers(admin.router, buy.router, payments.router, user.router)

    runner = web.AppRunner(create_app(bot))
    await runner.setup()
    await web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT).start()

    await services.set_commands(bot)
    expiry_task = asyncio.create_task(services.expiry_loop(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        expiry_task.cancel()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
