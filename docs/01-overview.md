# Breakfast Bot — Overview

A small Slack bot that logs weekend breakfast visits for Garrett, Greg, and Ian, tracks who's paid, and reports stats. All data lives in a Google Sheet — there's no database.

**Docs:**
1. Overview (this page)
2. [Setup & Running](02-setup.md)
3. [Commands & Data Reference](03-commands-and-data.md)

## What it does

- `/breakfast` opens a Slack modal to log a visit (restaurant, city, date, cost, who paid, star ratings from each member).
- Tracks a pay rotation (Garrett → Greg → Ian → Garrett) based on who paid last, and suggests the next payer.
- `/breakfast stats`, `/breakfast history`, and `/breakfast whopays` report on the logged data.
- Everything is written to and read from a single Google Sheet.

## How it's built

| Piece | Library | Role |
|---|---|---|
| Slack integration | [`slack-bolt`](https://slack.dev/bolt-python/) | Handles the `/breakfast` slash command and modal submission, via **Socket Mode** (no public URL/webhook needed) |
| Storage | [`gspread`](https://docs.gspread.org/) + `google-auth` | Reads/writes rows in a Google Sheet named `"Breakfast Log"` |

There's no local database, task queue, or web server. The bot is a single script (`bot.py`) that stays connected to Slack over a websocket and hits the Google Sheets API on demand.

## File structure

```
breakfast-bot/
├── bot.py              # everything: Slack handlers, Sheets I/O, stats logic
├── requirements.txt     # slack-bolt, gspread, google-auth
├── .gitignore           # excludes google_creds.json
└── docs/                # these docs
```

Everything lives in `bot.py`. There's no separate config file — configuration is a few constants at the top of the file plus environment variables (covered in [Setup](02-setup.md)).

## Request flow, end to end

1. Someone types `/breakfast` in Slack.
2. Slack sends the command to the bot over the Socket Mode websocket.
3. `handle_breakfast()` checks the subcommand text:
   - empty → opens the "Log Breakfast" modal (`build_log_modal`)
   - `stats` / `history` / `whopays` / `help` → posts a message directly, no modal
4. If the modal was opened and submitted, `handle_log_submission()` fires, appends a row to the Google Sheet via `append_row()`, and posts a confirmation message back to Slack.
5. Every read (`stats`, `history`, `whopays`, computing the next payer) calls `get_all_rows()`, which pulls the *entire* sheet fresh each time — there's no caching.

## Known quirks worth knowing about

These aren't bugs to necessarily fix, but they're worth knowing since this is a personal-reference doc:

- **Confirmation message goes to a DM, not the channel.** In `handle_log_submission`, `channel` is set to the user's ID (`body["user"]["id"]`), so the "✅ Breakfast logged!" message is sent as a DM to whoever filled out the modal, not posted in the channel where `/breakfast` was typed. The code has a comment acknowledging this and noting the fix (pass the channel through `private_metadata` on the modal).
- **No caching / no rate limiting.** Every command re-reads the whole sheet. Fine for 3 people logging breakfast on weekends; would need revisiting under heavier use.
- **Cost and ratings aren't validated.** The `cost` field is a free-text input — nothing stops someone from typing "forty dollars" instead of `40`. `stats` silently skips values it can't parse as a float.
- **Header write-on-first-append.** If the sheet is completely empty, `append_row()` writes a header row before writing data. If the sheet already has *any* content that isn't this bot's header, rows will misalign.
