from aiogram import BaseMiddleware

import db


class UserMW(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = data.get("event_from_user")
        if u and not u.is_bot:
            await db.ensure_user(u)
        return await handler(event, data)
