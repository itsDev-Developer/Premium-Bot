import json
import time

import aiosqlite

import config

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, joined_at INTEGER,
  wallet REAL DEFAULT 0, points INTEGER DEFAULT 0, referred_by INTEGER, banned INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT, ref TEXT,
  grp TEXT DEFAULT '', bundled INTEGER DEFAULT 0, active INTEGER DEFAULT 1, bot_token TEXT);
CREATE TABLE IF NOT EXISTS plans(
  category TEXT, dur TEXT, price REAL, new_user_price REAL, PRIMARY KEY(category, dur));
CREATE TABLE IF NOT EXISTS item_prices(
  item_id INTEGER, dur TEXT, price REAL, PRIMARY KEY(item_id, dur));
CREATE TABLE IF NOT EXISTS subs(
  user_id INTEGER, item_id INTEGER, expires_at INTEGER, reminded INTEGER DEFAULT 0,
  PRIMARY KEY(user_id, item_id));
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, dur TEXT, amount REAL,
  discount INTEGER DEFAULT 0, method TEXT, status TEXT, utr TEXT, proof_file_id TEXT,
  created_at INTEGER, paid_at INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_utr ON orders(utr) WHERE utr IS NOT NULL;
CREATE TABLE IF NOT EXISTS credits(
  utr TEXT PRIMARY KEY, amount REAL, claimed_by INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS offers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, percent INTEGER, ends_at INTEGER,
  active INTEGER DEFAULT 1);
"""

# Starter prices (INR). Edit any time with /setprice.
DEFAULT_PLANS = [
    # category, dur, price, new_user_price
    ("bot", "1d", 19, 15), ("bot", "15d", 39, None), ("bot", "1m", 59, None),
    ("bot", "3m", 149, None), ("bot", "6m", 279, None), ("bot", "12m", 499, None),
    ("bot", "life", 699, None),
    ("service", "1d", 49, 40), ("service", "15d", 100, None), ("service", "1m", 150, None),
    ("service", "3m", 399, None), ("service", "6m", 699, None), ("service", "12m", 799, None),
    ("service", "life", 999, None),
    ("channel", "15d", 100, None), ("channel", "1m", 199, None), ("channel", "2m", 349, None),
    ("channel", "3m", 499, None), ("channel", "6m", 899, None), ("channel", "9m", 1299, None),
    ("channel", "12m", 1599, None), ("channel", "life", 2500, None),
]


async def init():
    global _db
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    cur = await _db.execute("SELECT COUNT(*) FROM plans")
    if (await cur.fetchone())[0] == 0:
        await _db.executemany("INSERT INTO plans VALUES(?,?,?,?)", DEFAULT_PLANS)
    await _db.commit()


async def one(sql, *args):
    cur = await _db.execute(sql, args)
    row = await cur.fetchone()
    await cur.close()
    return row


async def all_(sql, *args):
    cur = await _db.execute(sql, args)
    rows = await cur.fetchall()
    await cur.close()
    return rows


async def run(sql, *args):
    """Execute + commit. Returns (lastrowid, rowcount)."""
    cur = await _db.execute(sql, args)
    await _db.commit()
    res = (cur.lastrowid, cur.rowcount)
    await cur.close()
    return res


async def ensure_user(u):
    await run(
        "INSERT INTO users(id, username, first_name, joined_at) VALUES(?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
        u.id, u.username, u.first_name, int(time.time()),
    )


async def items_by_ids(ids):
    ids = list(ids)
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return await all_(f"SELECT * FROM items WHERE id IN ({marks}) ORDER BY id", *ids)


async def names_for(ids):
    return [r["name"] for r in await items_by_ids(ids)]


def loads(s):
    return json.loads(s) if s else []
