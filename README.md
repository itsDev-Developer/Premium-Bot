# Premium Subscription Bot (Telegram)

Sells access to your **bots**, **service bots** and **private channels** — modelled on the bot in your video.
Python 3.10+ · aiogram 3 · SQLite (no external DB needed).

## Features
- `/start` home screen with photo + buttons (Buy, Mini App, Plan, Help, History, Proofs, Wallet, Support)
- Three stores: Bot Premium · Service Bots · Channel Premium
- Multi-select items, group buttons ("ALL …"), **Combo Plan**, combo discounts up to 60%
- Durations from 1 day to Lifetime; "new user" 1-day deal; flash sales (`/offers`)
- **Bot Premium gives bundled channels free** for the same duration
- Payments: UPI QR + UTR/screenshot, Telegram Stars (automatic), USDT (manual), wallet
- Auto-verification of UPI via a webhook (see below); otherwise admin taps Approve/Reject
- Auto access: single-use 24h invite links for channels; "Start bot" buttons for bots
- Expiry job: renewal reminder 24h before, removes expired users from channels
- Wallet + points, `/refer` referral bonus, `/history`, `/plan`
- Admin: `/users /broadcast /payments /addpremium /rmpremium /premium_users /user /additem /addbot /chnls /removebot /remote_bots /bot_token /invite /commands /offers /addbalance /rmbalance /verify_pay /manual_pay /check_utr /setprice /payment_clear`

## 1. Setup
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env
python main.py
```
1. Create the bot in **@BotFather**, put the token in `.env` as `BOT_TOKEN`.
2. Get your numeric Telegram id (e.g. from @userinfobot) → `ADMIN_IDS`.
3. Set `UPI_ID` (and optionally `USDT_ADDRESS`). Stars work with no setup.
4. Add the bot as **admin** in every private channel you sell (permissions: *Invite users* and *Ban users*).

## 2. Add what you sell (from Telegram, as admin)
```
/additem bot|Alya|AlyaFileBot|adult
/additem service|Manga Bot|MangaBotUsername
/additem channel|Movies Database|-1001234567890|movies|1
/remote_bots                          # shows item ids
/setprice bot 1m 59                   # edit any plan price
/setprice bot 1d 19 15                # 1-day price + new-user price
/setprice item 3 1m 99                # price override for one item
/offers add Weekend Sale|30|48        # 30% off for 48 hours
```
`group` creates an "ALL GROUP" button. `bundled=1` (channels) = free with any Bot Premium purchase.
Starter prices are placeholders (only some came from your video) — change them with `/setprice`.

## 3. Payments
- **Stars**: fully automatic. Adjust `STARS_PER_USD` in `.env` to match current Stars pricing.
- **UPI (manual)**: user sends UTR or screenshot → you get Approve/Reject buttons.
- **UPI (automatic)**: POST bank credits to your bot and it matches the UTR + amount instantly:
  ```bash
  curl -X POST https://YOUR-DOMAIN/webhook/credit \
    -H "X-Secret: $WEBHOOK_SECRET" -H "Content-Type: application/json" \
    -d '{"utr":"123456789012","amount":59}'
  ```
  Feed it from a payment gateway / bank-alert forwarder you trust. Put the bot behind HTTPS (Caddy/nginx).
- **USDT**: user submits the tx hash with `/bought TXID`; you verify and approve.

## 4. Let your other bots check premium
```
GET https://YOUR-DOMAIN/api/premium?user_id=123&item=AlyaFileBot
Header: X-Api-Key: <API_KEY>
→ {"ok": true, "premium": true, "expires_at": 1767225600}
```

## 5. Run 24/7
Use a VPS with `systemd`, `pm2` or Docker. Back up `premium.db` regularly.

## Not included
- The Telegram **Mini App** UI (the button appears once you set `MINIAPP_URL`).
- Bank/UPI verification without your own webhook feed (no public UPI API exists).
- The video's `/update` command (deploy updates with git/your process manager instead).

## Responsible use
Only sell content you own or have the rights to distribute, follow Telegram's Terms of Service, and keep adult
material age-restricted and legal where you operate. You are responsible for refunds and local tax rules.
