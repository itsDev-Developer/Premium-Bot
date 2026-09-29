import math
import time

import config
import db

# key -> (days, label). days=None means lifetime.
DURATIONS = {
    "1d": (1, "1 Day"), "15d": (15, "15 Days"), "1m": (30, "1 Month"), "2m": (60, "2 Months"),
    "3m": (90, "3 Months"), "6m": (180, "6 Months"), "9m": (270, "9 Months"),
    "12m": (365, "12 Months"), "life": (None, "Lifetime"),
}
ORDER = list(DURATIONS)


def label(dur: str) -> str:
    return DURATIONS[dur][1]


def days(dur: str):
    return DURATIONS[dur][0]


def money(x) -> str:
    x = float(x)
    return f"₹{int(x)}" if x == int(x) else f"₹{x:.2f}"


def combo_pct(n: int) -> int:
    pct = 0
    for count, p in config.COMBO_TIERS:
        if n >= count:
            pct = p
    return pct


def stars_for(inr: float) -> int:
    return max(1, math.ceil(inr / config.INR_PER_USD * config.STARS_PER_USD))


async def plan_durs(cat: str):
    have = {r["dur"] for r in await db.all_("SELECT dur FROM plans WHERE category=?", cat)}
    return [d for d in ORDER if d in have]


async def best_flash() -> int:
    r = await db.one(
        "SELECT COALESCE(MAX(percent),0) p FROM offers WHERE active=1 AND ends_at>?", int(time.time())
    )
    return int(r["p"])


async def quote(uid: int, ids, dur: str):
    """Price a selection. Returns None if the selection/duration is invalid."""
    ids = list(ids)
    if not ids or dur not in DURATIONS:
        return None
    marks = ",".join("?" * len(ids))
    items = await db.all_(f"SELECT * FROM items WHERE id IN ({marks}) AND active=1", *ids)
    if len(items) != len(ids):
        return None
    cats = {i["category"] for i in items}
    if len(cats) != 1:
        return None
    cat = cats.pop()
    plan = await db.one("SELECT * FROM plans WHERE category=? AND dur=?", cat, dur)
    if not plan:
        return None
    is_new = await db.one("SELECT 1 FROM orders WHERE user_id=? AND status='paid' LIMIT 1", uid) is None
    subtotal = 0.0
    for it in items:
        ov = await db.one("SELECT price FROM item_prices WHERE item_id=? AND dur=?", it["id"], dur)
        if ov:
            p = ov["price"]
        elif dur == "1d" and is_new and plan["new_user_price"] is not None:
            p = plan["new_user_price"]
        else:
            p = plan["price"]
        subtotal += p
    combo = combo_pct(len(items))
    flash = await best_flash()
    disc = min(config.MAX_DISCOUNT, combo + flash)
    total = max(1, round(subtotal * (1 - disc / 100)))
    return {"cat": cat, "items": items, "subtotal": subtotal, "combo": combo,
            "flash": flash, "disc": disc, "total": total}
