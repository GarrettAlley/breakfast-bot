# Setup & Running

[← Overview](01-overview.md) | [Commands & Data Reference →](03-commands-and-data.md)

This covers everything needed to get the bot running from scratch: the Slack app, the Google Sheet, credentials, and starting the process.

## 1. Prerequisites

- Python 3.9+
- A Slack workspace where you can install apps
- A Google account that can create a Sheet and a service account (via Google Cloud Console)

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `slack-bolt`, `gspread`, and `google-auth`.

## 3. Create the Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Enable **Socket Mode** (Settings → Socket Mode). This lets the bot run without a public HTTPS endpoint. Generate an **app-level token** with the `connections:write` scope — this is your `SLACK_APP_TOKEN` (starts with `xapp-`).
3. Under **OAuth & Permissions**, add these bot token scopes:
   - `commands` — to receive the `/breakfast` slash command
   - `chat:write` — to post messages
4. Under **Slash Commands**, create `/breakfast`. The request URL doesn't matter with Socket Mode, but Slack requires you to fill in something.
5. **Interactivity & Shortcuts** must be turned on (Socket Mode handles this automatically once enabled, but confirm it's on) — this is what allows the modal (`views_open` / `view_submission`) to work.
6. Install the app to your workspace. Copy the **Bot User OAuth Token** (starts with `xoxb-`) — this is your `SLACK_BOT_TOKEN`.

## 4. Create the Google Sheet + service account

1. Create a new Google Sheet named exactly **`Breakfast Log`** (the name is hardcoded in `bot.py` as `SHEET_NAME`). You can leave it empty — the bot writes the header row itself on the first log.
2. In [Google Cloud Console](https://console.cloud.google.com/), create a project (or reuse one) and enable the **Google Sheets API** and **Google Drive API**.
3. Create a **service account** (IAM & Admin → Service Accounts). Create a JSON key for it and download it.
4. Share the `Breakfast Log` sheet with the service account's email address (found in the JSON key file, field `client_email`), with **Editor** access.

## 5. Provide credentials to the bot

`get_sheet()` in `bot.py` looks for credentials in one of two ways, in this order:

1. **Environment variable** `GOOGLE_CREDS_JSON` — the *entire contents* of the service account JSON key, as a string.
2. **Local file** `google_creds.json` — if the env var isn't set, it reads this file from the working directory. This file is already in `.gitignore`, so it's safe to drop it in the repo folder for local runs without risk of committing it.

Pick whichever fits where you're running it — a local file for running on your own machine, the env var for anywhere secrets are set via environment (e.g. a hosting platform's dashboard).

## 6. Environment variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot token, starts with `xoxb-` |
| `SLACK_APP_TOKEN` | Yes | App-level token for Socket Mode, starts with `xapp-` |
| `GOOGLE_CREDS_JSON` | No* | Full service account JSON as a string. *Required if not using `google_creds.json` file. |

## 7. Run it

```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
export GOOGLE_CREDS_JSON="$(cat google_creds.json)"   # or just leave google_creds.json in place instead

python bot.py
```

You should see:

```
⚡ Breakfast Bot is running!
```

The process stays running and connected over the websocket — it needs to keep running for the slash command to work (there's no serverless/on-demand mode here). For anything beyond local testing, run it under something that keeps it alive (`systemd`, `pm2`, a small always-on VM/container, etc.) and restarts it if it crashes.

## Troubleshooting

- **Slash command does nothing in Slack:** double-check Socket Mode is enabled and the app-level token has `connections:write`. Check the terminal running `bot.py` for errors.
- **`SpreadsheetNotFound` error:** the sheet name must be exactly `Breakfast Log`, and it must be shared with the service account's email.
- **`PermissionError` / 403 from Google:** the service account needs Editor access on the sheet, and both the Sheets API and Drive API need to be enabled on the Google Cloud project.
- **Modal opens but submitting does nothing / errors:** check that Interactivity is enabled for the Slack app.
