import asyncio
import logging
import time

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

import config
import db
from pricing import days, label, money
from ui import btn, esc, fmt_ts, kb

log = logging.getLogger("premium")

USER_CMDS = [
    ("start", "Start bot"), ("plan", "Check premium subscription"),
    ("offer", "Check active flash sales"), ("myplan", "Check premium subscription"),
    ("bought", "Submit payment screenshot / UTR"), ("admin", "Contact support"),
    ("refer", "Invite your friends and earn"), ("shop", "Points to wallet balance"),
]
ADMIN_CMDS = USER_CMDS + [
    ("users", "Users setting"), ("broadcast", "Broadcast message"), ("cancel", "Cancel broadcast"),
    ("payments", "Check payment stats"), ("payment_clear", "Clear unpaid orders"),
    ("chnls", "Manage channels"), ("addpremium", "Add premium user"),
    ("rmpremium", "Remove premium user"), ("premium_users", "List premium users"),
    ("user", "Reply to user message"), ("addbot", "Add a new bot"), ("additem", "Add any item"),
    ("bot_token", "Set bot token"), ("invite", "Get invite / deep link"),
    ("removebot", "Remove an item"), ("remote_bots", "List all items"),
    ("commands", "Update bot commands"), ("offers", "Manage flash sales"),
    ("addbalance", "Add wallet balance"), ("rmbalance", "Remove wallet balance"),
    ("verify_pay", "Approve/reject an order"), ("manual_pay", "Manually credit a payment"),
    ("check_utr", "Check if UTR is claimed"), ("setprice", "Set plan price"),
]


def chat_ref(ref: str):
    ref = (ref or "").strip()
    return int(ref) if ref.lstrip("-").isdigit() else "@" + ref.lstrip("@")


async def safe_send(bot: Bot, uid: int, text: str, markup=None):
    try:
        await bot.send_message(uid, text, reply_markup=markup)
        return True
    except Exception as e:  # blocked user, deleted chat, etc.
        log.warning("send to %s failed: %s", uid, e)
        return False


async def notify_admins(bot: Bot, text: str, markup=None, photo: str | None = None):
    for a in config.ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(a, photo, caption=text, reply_markup=markup)
            else:
                await bot.send_message(a, text, reply_markup=markup)
        except Exception as e:
            log.warning("admin notify %s failed: %s", a, e)


async def set_commands(bot: Bot):
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in USER_CMDS])
    for a in config.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in ADMIN_CMDS],
                scope=BotCommandScopeChat(chat_id=a),
            )
        except Exception as e:
            log.warning("admin commands for %s not set: %s", a, e)


async def make_invite(bot: Bot, ref: str, user_id: int):
    try:
        link = await bot.create_chat_invite_link(
            chat_id=chat_ref(ref), member_limit=1,
            expire_date=int(time.time()) + 86400, name=f"u{user_id}",
        )
        return link.invite_link
    except Exception as e:
        log.warning("invite for %s failed (is the bot admin there?): %s", ref, e)
        return None


async def grant(user_id: int, item_id: int, dur: str):
    d = days(dur)
    row = await db.one("SELECT expires_at FROM subs WHERE user_id=? AND item_id=?", user_id, item_id)
    now = int(time.time())
    if d is None:
        new = None
    else:
        if row is not None and row["expires_at"] is None:
            return  # already lifetime
        base = max(now, row["expires_at"]) if row is not None else now
        new = base + d * 86400
    await db.run(
        "INSERT INTO subs(user_id,item_id,expires_at,reminded) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id,item_id) DO UPDATE SET expires_at=excluded.expires_at, reminded=excluded.reminded",
        user_id, item_id, new, 1 if dur == "1d" else 0,
    )


async def activate_order(bot: Bot, oid: int) -> bool:
    """Mark paid (once), grant access, send links, award points/referral. Idempotent."""
    now = int(time.time())
    _, rc = await db.run(
        "UPDATE orders SET status='paid', paid_at=? WHERE id=? AND status!='paid'", now, oid
    )
    if rc != 1:
        return False
    o = await db.one("SELECT * FROM orders WHERE id=?", oid)
    uid = o["user_id"]
    ids = db.loads(o["items"])
    items = list(await db.items_by_ids(ids))
    bonus = []
    if any(i["category"] == "bot" for i in items):  # Bot Premium => bundled channels free
        bonus = [r for r in await db.all_(
            "SELECT * FROM items WHERE category='channel' AND bundled=1 AND active=1"
        ) if r["id"] not in ids]
    bonus_ids = {b["id"] for b in bonus}
    for it in items + bonus:
        await grant(uid, it["id"], o["dur"])

    pts = int(o["amount"] * config.POINTS_PER_INR)
    await db.run("UPDATE users SET points=points+? WHERE id=?", pts, uid)

    u = await db.one("SELECT referred_by, first_name FROM users WHERE id=?", uid)
    n_paid = (await db.one("SELECT COUNT(*) c FROM orders WHERE user_id=? AND status='paid'", uid))["c"]
    if u and u["referred_by"] and n_paid == 1 and config.REFERRAL_BONUS_POINTS:
        await db.run("UPDATE users SET points=points+? WHERE id=?",
                     config.REFERRAL_BONUS_POINTS, u["referred_by"])
        await safe_send(bot, u["referred_by"],
                        f"🎁 Your friend just made a purchase! You earned <b>{config.REFERRAL_BONUS_POINTS} points</b>.")

    lines, rows = [], []
    for it in items + bonus:
        sub = await db.one("SELECT expires_at FROM subs WHERE user_id=? AND item_id=?", uid, it["id"])
        tag = " 🎁 <i>free bonus</i>" if it["id"] in bonus_ids else ""
        lines.append(f"• <b>{esc(it['name'])}</b> — until {fmt_ts(sub['expires_at'])}{tag}")
        if it["category"] == "channel":
            link = await make_invite(bot, it["ref"], uid)
            if link:
                rows.append([btn(f"🔗 Join {it['name']}", url=link)])
            else:
                lines.append("  ⚠️ couldn't create the invite link — contact support.")
        elif it["ref"]:
            rows.append([btn(f"▶️ Start {it['name']}", url=f"https://t.me/{it['ref'].lstrip('@')}?start=premium")])
    text = ("✅ <b>Payment confirmed — premium activated!</b>\n\n" + "\n".join(lines) +
            f"\n\n💰 You earned <b>{pts} points</b>.")
    if any(i["category"] != "channel" for i in items):
        text += "\n\n⚠️ <b>Important:</b> first press START on each bot above, or premium won't apply there."
    if any(i["category"] == "channel" for i in items + bonus):
        text += "\n⏳ Invite links are single-use and expire in 24 hours."
    await safe_send(bot, uid, text, kb(rows) if rows else None)
    await notify_admins(
        bot, f"💰 Order #{oid} paid — {money(o['amount'])} · {label(o['dur'])} · "
             f"user <code>{uid}</code> · {esc(o['method'] or '-')}"
    )
    return True


async def reject_order(bot: Bot, oid: int) -> bool:
    _, rc = await db.run("UPDATE orders SET status='rejected' WHERE id=? AND status!='paid'", oid)
    if rc != 1:
        return False
    o = await db.one("SELECT user_id FROM orders WHERE id=?", oid)
    await safe_send(bot, o["user_id"],
                    f"❌ We couldn't verify the payment for order #{oid}. "
                    "If you paid, please contact support with your screenshot.")
    return True


async def settle_utr(bot: Bot, oid: int, utr: str) -> bool:
    """If a bank credit with this UTR (and enough amount) exists, activate the order."""
    o = await db.one("SELECT * FROM orders WHERE id=?", oid)
    if not o or o["status"] == "paid":
        return False
    c = await db.one("SELECT * FROM credits WHERE utr=? AND claimed_by IS NULL", utr)
    if not c or c["amount"] < o["amount"] - 0.99:
        return False
    _, rc = await db.run(
        "UPDATE credits SET claimed_by=? WHERE utr=? AND claimed_by IS NULL", o["user_id"], utr
    )
    if rc != 1:
        return False
    await db.run("UPDATE orders SET utr=?, method=COALESCE(method,'upi') WHERE id=?", utr, oid)
    return await activate_order(bot, oid)


# ---------------- expiry ----------------
async def run_expiry(bot: Bot):
    now = int(time.time())
    soon = now + 86400
    rows = await db.all_(
        "SELECT s.user_id, s.expires_at, i.name FROM subs s JOIN items i ON i.id=s.item_id "
        "WHERE s.expires_at IS NOT NULL AND s.reminded=0 AND s.expires_at>? AND s.expires_at<=?",
        now, soon,
    )
    by_user: dict[int, list] = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r)
    for uid, rs in by_user.items():
        body = "\n".join(f"• {esc(r['name'])} — {fmt_ts(r['expires_at'])}" for r in rs)
        await safe_send(bot, uid, f"⏰ <b>Your premium expires soon</b>\n\n{body}\n\nRenew anytime with /start.")
        await db.run("UPDATE subs SET reminded=1 WHERE user_id=? AND expires_at>? AND expires_at<=?",
                     uid, now, soon)

    rows = await db.all_(
        "SELECT s.user_id, s.item_id, i.name, i.category, i.ref FROM subs s "
        "JOIN items i ON i.id=s.item_id WHERE s.expires_at IS NOT NULL AND s.expires_at<=?", now,
    )
    gone: dict[int, list] = {}
    for r in rows:
        if r["category"] == "channel":
            try:  # ban + unban = remove from channel but allow re-joining after renewal
                await bot.ban_chat_member(chat_ref(r["ref"]), r["user_id"])
                await bot.unban_chat_member(chat_ref(r["ref"]), r["user_id"], only_if_banned=True)
            except Exception as e:
                log.warning("remove %s from %s failed: %s", r["user_id"], r["ref"], e)
        await db.run("DELETE FROM subs WHERE user_id=? AND item_id=?", r["user_id"], r["item_id"])
        gone.setdefault(r["user_id"], []).append(r["name"])
    for uid, names in gone.items():
        await safe_send(bot, uid, "⌛ <b>Premium expired</b>\n\n" +
                        "\n".join(f"• {esc(n)}" for n in names) + "\n\nRenew with /start.")


async def expiry_loop(bot: Bot):
    while True:
        try:
            await run_expiry(bot)
        except Exception:
            log.exception("expiry job failed")
        await asyncio.sleep(1800)
