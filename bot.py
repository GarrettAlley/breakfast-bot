"""
Breakfast Bot - Track weekend breakfast visits for Garrett, Greg, and Ian
Uses Slack Bolt (Socket Mode) + Google Sheets
"""

import os
import json
import re
from datetime import date
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import gspread
from google.oauth2.service_account import Credentials

# ── Config ──────────────────────────────────────────────────────────────────
MEMBERS = ["Garrett", "Greg", "Ian"]
SHEET_NAME = "Breakfast Log"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]

app = App(token=os.environ["SLACK_BOT_TOKEN"])

# ── Google Sheets helper ─────────────────────────────────────────────────────
def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_json:
        import json
        creds_info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("google_creds.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open(SHEET_NAME)
    return sh.sheet1

def get_all_rows():
    sheet = get_sheet()
    rows = sheet.get_all_values()
    if len(rows) <= 1:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]

def append_row(data: dict):
    sheet = get_sheet()
    rows = sheet.get_all_values()
    if len(rows) == 0:
        # Write header if sheet is empty
        sheet.append_row([
            "Date", "Restaurant", "City", "Cost",
            "Paid By", "Garrett Rating", "Greg Rating", "Ian Rating"
        ])
    sheet.append_row([
        data["date"], data["restaurant"], data["city"], data["cost"],
        data["paid_by"],
        data.get("rating_Garrett", ""),
        data.get("rating_Greg", ""),
        data.get("rating_Ian", ""),
    ])

def get_next_payer():
    rows = get_all_rows()
    if not rows:
        return MEMBERS[0]
    # Find who paid most recently and return the next person in rotation
    last_payer = rows[-1].get("Paid By", "")
    if last_payer in MEMBERS:
        idx = MEMBERS.index(last_payer)
        return MEMBERS[(idx + 1) % len(MEMBERS)]
    return MEMBERS[0]

# ── In-memory state for multi-step modal flow ────────────────────────────────
pending = {}  # keyed by user_id

# ── /breakfast command ───────────────────────────────────────────────────────
@app.command("/breakfast")
def handle_breakfast(ack, body, client):
    ack()
    subcommand = body.get("text", "").strip().lower()
    user_id = body["user_id"]

    if subcommand == "stats":
        show_stats(body, client)
    elif subcommand == "history":
        show_history(body, client)
    elif subcommand == "help":
        show_help(body, client)
    elif subcommand == "whopays":
        show_who_pays(body, client)
    else:
        # Default: open the log modal
        next_payer = get_next_payer()
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_log_modal(next_payer)
        )

def build_log_modal(suggested_payer):
    today = date.today().isoformat()
    payer_options = [
        {"text": {"type": "plain_text", "text": m}, "value": m}
        for m in MEMBERS
    ]
    star_options = [
        {"text": {"type": "plain_text", "text": f"{'⭐' * i} ({i})"}, "value": str(i)}
        for i in range(1, 6)
    ]

    return {
        "type": "modal",
        "callback_id": "log_breakfast",
        "title": {"type": "plain_text", "text": "🍳 Log Breakfast"},
        "submit": {"type": "plain_text", "text": "Log It"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input", "block_id": "restaurant",
                "label": {"type": "plain_text", "text": "Restaurant"},
                "element": {"type": "plain_text_input", "action_id": "value",
                            "placeholder": {"type": "plain_text", "text": "e.g. Sunny Side Café"}}
            },
            {
                "type": "input", "block_id": "city",
                "label": {"type": "plain_text", "text": "City"},
                "element": {"type": "plain_text_input", "action_id": "value",
                            "placeholder": {"type": "plain_text", "text": "e.g. San Jose"}}
            },
            {
                "type": "input", "block_id": "visit_date",
                "label": {"type": "plain_text", "text": "Date"},
                "element": {"type": "plain_text_input", "action_id": "value",
                            "initial_value": today,
                            "placeholder": {"type": "plain_text", "text": "YYYY-MM-DD"}}
            },
            {
                "type": "input", "block_id": "cost",
                "label": {"type": "plain_text", "text": "Total Cost ($)"},
                "element": {"type": "plain_text_input", "action_id": "value",
                            "placeholder": {"type": "plain_text", "text": "e.g. 47.50"}}
            },
            {
                "type": "input", "block_id": "paid_by",
                "label": {"type": "plain_text", "text": f"Who Paid? (suggested: {suggested_payer})"},
                "element": {
                    "type": "static_select", "action_id": "value",
                    "initial_option": {"text": {"type": "plain_text", "text": suggested_payer}, "value": suggested_payer},
                    "options": payer_options
                }
            },
            {"type": "divider"},
            {
                "type": "input", "block_id": "rating_Garrett",
                "label": {"type": "plain_text", "text": "Garrett's Rating"},
                "element": {"type": "static_select", "action_id": "value", "options": star_options}
            },
            {
                "type": "input", "block_id": "rating_Greg",
                "label": {"type": "plain_text", "text": "Greg's Rating"},
                "element": {"type": "static_select", "action_id": "value", "options": star_options}
            },
            {
                "type": "input", "block_id": "rating_Ian",
                "label": {"type": "plain_text", "text": "Ian's Rating"},
                "element": {"type": "static_select", "action_id": "value", "options": star_options}
            },
        ]
    }

# ── Modal submission ─────────────────────────────────────────────────────────
@app.view("log_breakfast")
def handle_log_submission(ack, body, client):
    ack()
    vals = body["view"]["state"]["values"]

    def text(block): return vals[block]["value"]["value"]
    def select(block): return vals[block]["value"]["selected_option"]["value"]

    data = {
        "restaurant": text("restaurant"),
        "city":       text("city"),
        "date":       text("visit_date"),
        "cost":       text("cost"),
        "paid_by":    select("paid_by"),
        "rating_Garrett": select("rating_Garrett"),
        "rating_Greg":    select("rating_Greg"),
        "rating_Ian":     select("rating_Ian"),
    }

    append_row(data)

    ratings_str = " | ".join(
        f"{m}: {'⭐' * int(data[f'rating_{m}'])}"
        for m in MEMBERS
    )
    next_payer = get_next_payer()

    # Post confirmation to the channel where /breakfast was typed
    channel = body["user"]["id"]  # fallback to DM; ideally pass channel via private_metadata
    client.chat_postMessage(
        channel=channel,
        text=(
            f"✅ *Breakfast logged!*\n"
            f"📍 {data['restaurant']}, {data['city']}\n"
            f"📅 {data['date']}  |  💵 ${data['cost']}  |  Paid by: *{data['paid_by']}*\n"
            f"⭐ {ratings_str}\n\n"
            f"_Next up to pay: *{next_payer}*_"
        )
    )

# ── Help ─────────────────────────────────────────────────────────────────────
def show_help(body, client):
    client.chat_postMessage(
        channel=body["channel_id"],
        text=(
            "*🍳 Breakfast Bot — Commands*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "`/breakfast` — Log a new breakfast visit. Opens a form to enter the restaurant, city, date, cost, who paid, and ratings (1–5 ⭐) for Garrett, Greg, and Ian.\n"
            "`/breakfast stats` — Show overall stats: total visits, spending, pay rotation counts, average ratings, and top-rated restaurant.\n"
            "`/breakfast history` — Show the last 5 visits.\n"
            "`/breakfast whopays` — Quick one-liner showing whose turn it is to pay.\n"
            "`/breakfast help` — Show this message.\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "_Only one person should log each visit to avoid duplicate entries. "
            "Pay rotation goes Garrett → Greg → Ian → Garrett, based on who paid last._"
        )
    )

# ── Who Pays ──────────────────────────────────────────────────────────────────
def show_who_pays(body, client):
    next_payer = get_next_payer()
    client.chat_postMessage(
        channel=body["channel_id"],
        text=f"💳 It's *{next_payer}*'s turn to pay."
    )


def show_stats(body, client):
    rows = get_all_rows()
    if not rows:
        client.chat_postMessage(
            channel=body["channel_id"],
            text="No breakfasts logged yet! Use `/breakfast` to log your first one."
        )
        return

    total_visits = len(rows)
    costs = []
    for r in rows:
        try:
            costs.append(float(str(r.get("Cost", "0")).replace("$", "")))
        except ValueError:
            pass

    total_spent = sum(costs)
    avg_cost = total_spent / len(costs) if costs else 0

    # Pay counts
    pay_counts = {m: 0 for m in MEMBERS}
    for r in rows:
        p = r.get("Paid By", "")
        if p in pay_counts:
            pay_counts[p] += 1
    pay_str = "  |  ".join(f"{m}: {pay_counts[m]}x" for m in MEMBERS)

    # Average ratings per member
    rating_totals = {m: [] for m in MEMBERS}
    for r in rows:
        for m in MEMBERS:
            val = r.get(f"{m} Rating", "")
            try:
                rating_totals[m].append(float(val))
            except (ValueError, TypeError):
                pass
    rating_str = "  |  ".join(
        f"{m}: {sum(rating_totals[m])/len(rating_totals[m]):.1f}⭐" if rating_totals[m] else f"{m}: —"
        for m in MEMBERS
    )

    # Top restaurant
    from collections import Counter, defaultdict
    rest_ratings = defaultdict(list)
    for r in rows:
        name = r.get("Restaurant", "")
        for m in MEMBERS:
            try:
                rest_ratings[name].append(float(r.get(f"{m} Rating", "")))
            except (ValueError, TypeError):
                pass
    if rest_ratings:
        top_rest = max(rest_ratings, key=lambda k: sum(rest_ratings[k]) / len(rest_ratings[k]))
        top_avg = sum(rest_ratings[top_rest]) / len(rest_ratings[top_rest])
        top_str = f"{top_rest} (avg {top_avg:.1f}⭐)"
    else:
        top_str = "—"

    last_row = rows[-1]
    next_payer = get_next_payer()

    client.chat_postMessage(
        channel=body["channel_id"],
        text=(
            f"*🍳 Breakfast Stats*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Total visits: *{total_visits}*\n"
            f"💵 Total spent: *${total_spent:.2f}*  |  Avg/visit: *${avg_cost:.2f}*\n"
            f"🏆 Top spot: *{top_str}*\n"
            f"📅 Last visit: *{last_row.get('Date', '?')}* at {last_row.get('Restaurant', '?')}\n"
            f"💳 Pay counts: {pay_str}\n"
            f"⭐ Avg ratings: {rating_str}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"_Next up to pay: *{next_payer}*_"
        )
    )

# ── History ──────────────────────────────────────────────────────────────────
def show_history(body, client):
    rows = get_all_rows()
    if not rows:
        client.chat_postMessage(
            channel=body["channel_id"],
            text="No breakfasts logged yet!"
        )
        return

    last5 = rows[-5:][::-1]
    lines = ["*🍳 Last 5 Breakfasts*", "━━━━━━━━━━━━━━━━━━━"]
    for r in last5:
        avg_rating = []
        for m in MEMBERS:
            try:
                avg_rating.append(float(r.get(f"{m} Rating", "")))
            except (ValueError, TypeError):
                pass
        avg = f"{sum(avg_rating)/len(avg_rating):.1f}⭐" if avg_rating else "—"
        lines.append(
            f"📅 {r.get('Date','?')}  📍 {r.get('Restaurant','?')}, {r.get('City','?')}  "
            f"💵 ${r.get('Cost','?')}  {avg}"
        )
    client.chat_postMessage(channel=body["channel_id"], text="\n".join(lines))

# ── Start ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡ Breakfast Bot is running!")
    handler.start()
