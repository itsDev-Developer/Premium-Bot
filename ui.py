import html
from datetime import datetime, timezone

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message, WebAppInfo)


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def btn(text, cb=None, url=None, web=None):
    if url:
        return InlineKeyboardButton(text=text, url=url)
    if web:
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=web))
    return InlineKeyboardButton(text=text, callback_data=cb)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chunk(buttons, n=2):
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


def back_close(back_cb: str):
    return [btn("⬅️ BACK", back_cb), btn("✖️ CLOSE", "close")]


def fmt_ts(ts) -> str:
    if ts is None:
        return "Lifetime ♾"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def fmt_date(ts) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d %b %Y")


async def render(cb: CallbackQuery, text: str, markup=None):
    """Edit the tapped message in place (text or photo caption); fall back to resend."""
    m = cb.message
    if not isinstance(m, Message):
        await cb.answer("This message is too old. Send /start again.", show_alert=True)
        return
    try:
        if m.photo:
            await m.edit_caption(caption=text, reply_markup=markup)
        else:
            await m.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" in str(e).lower():
            return
        try:
            await m.delete()
        except Exception:
            pass
        await m.answer(text, reply_markup=markup)
