import hmac
import time

from aiohttp import web

import config
import db
import services


def _eq(a: str, b: str) -> bool:
    return bool(b) and hmac.compare_digest(a or "", b)


def create_app(bot) -> web.Application:
    app = web.Application()

    async def health(_):
        return web.json_response({"ok": True})

    async def credit(req: web.Request):
        """Your bank/SMS forwarder posts {"utr": "...", "amount": 59} here (header X-Secret)."""
        if not _eq(req.headers.get("X-Secret", ""), config.WEBHOOK_SECRET):
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)
        try:
            data = await req.json()
            utr = str(data["utr"]).strip()
            amount = float(data["amount"])
        except Exception:
            return web.json_response({"ok": False, "error": "need utr and amount"}, status=400)
        await db.run("INSERT OR IGNORE INTO credits(utr, amount, created_at) VALUES(?,?,?)",
                     utr, amount, int(time.time()))
        matched = False
        o = await db.one("SELECT id FROM orders WHERE utr=? AND status='pending_review'", utr)
        if o:
            matched = await services.settle_utr(bot, o["id"], utr)
        return web.json_response({"ok": True, "matched": matched})

    async def premium(req: web.Request):
        """Other bots ask: GET /api/premium?user_id=123&item=bot_username  (header X-Api-Key)."""
        if not _eq(req.headers.get("X-Api-Key", ""), config.API_KEY):
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)
        try:
            uid = int(req.query["user_id"])
        except Exception:
            return web.json_response({"ok": False, "error": "user_id required"}, status=400)
        sql = ("SELECT s.expires_at FROM subs s JOIN items i ON i.id=s.item_id "
               "WHERE s.user_id=? AND (s.expires_at IS NULL OR s.expires_at>?)")
        args = [uid, int(time.time())]
        item = req.query.get("item", "").strip().lstrip("@")
        if item:
            sql += " AND lower(i.ref)=lower(?)"
            args.append(item)
        rows = await db.all_(sql, *args)
        exp = None if any(r["expires_at"] is None for r in rows) else (max((r["expires_at"] for r in rows), default=None))
        return web.json_response({"ok": True, "premium": bool(rows), "expires_at": exp})

    app.router.add_get("/", health)
    app.router.add_post("/webhook/credit", credit)
    app.router.add_get("/api/premium", premium)
    return app
