# Commands & Data Reference

[← Setup & Running](02-setup.md) | [Overview](01-overview.md)

## Commands

All commands are subcommands of `/breakfast`, dispatched in `handle_breakfast()` by matching the trimmed, lowercased text after the command.

| Command | What it does |
|---|---|
| `/breakfast` | Opens the "Log Breakfast" modal. |
| `/breakfast stats` | Posts total visits, total/average spend, top-rated restaurant, last visit, pay counts per person, and average rating per person. |
| `/breakfast history` | Posts the last 5 visits (most recent first): date, restaurant, city, cost, average rating. |
| `/breakfast whopays` | Posts a one-line message naming whose turn it is to pay. |
| `/breakfast help` | Posts the command list. |

Anything else typed after `/breakfast` falls through to the default case and opens the log modal (the text is otherwise ignored).

### Logging a breakfast (the modal)

Fields, in order:

1. **Restaurant** — free text
2. **City** — free text
3. **Date** — free text, pre-filled with today's date (`YYYY-MM-DD`); *not validated as a real date*
4. **Total Cost ($)** — free text; *not validated as a number* (parsed later, silently skipped in `stats` if it's not a valid float)
5. **Who Paid?** — dropdown of the three members, pre-selected with the suggested next payer
6. **Garrett's / Greg's / Ian's Rating** — three separate dropdowns, 1–5 stars each, no default selection (all three are required to submit)

On submit, the row is appended to the sheet and a confirmation is sent — as a DM to the submitter, not the channel (see the note in [Overview](01-overview.md#known-quirks-worth-knowing-about)).

## Pay rotation logic

`get_next_payer()`:
1. If the sheet has no rows yet, the next payer is `MEMBERS[0]` (Garrett).
2. Otherwise, it looks at the `Paid By` value of the **last row in the sheet** and returns the next name in the `MEMBERS` list (`["Garrett", "Greg", "Ian"]`), wrapping around.
3. If the last `Paid By` value isn't one of the three known names (e.g. sheet was edited by hand with a typo), it falls back to Garrett.

This is a pure rotation based on the most recent row — it doesn't count how many times each person has paid overall to "balance" things; `stats`' pay-count breakdown is just for visibility, not used to determine the suggested next payer.

## Google Sheet data model

The sheet `Breakfast Log` (sheet1) is written and read as plain rows, with the header written automatically on the first log if the sheet is empty:

| Column | Written as | Notes |
|---|---|---|
| `Date` | string, whatever was typed in the modal | Not validated — could be any string |
| `Restaurant` | string | |
| `City` | string | |
| `Cost` | string, whatever was typed | Parsed as float later; `$` is stripped before parsing in `stats` |
| `Paid By` | one of `Garrett`/`Greg`/`Ian` | Constrained by the dropdown |
| `Garrett Rating` | `"1"`–`"5"` | Note: the sheet header is `"Garrett Rating"` but internally the code uses the key `rating_Garrett` — see below |
| `Greg Rating` | `"1"`–`"5"` | |
| `Ian Rating` | `"1"`–`"5"` | |

**Naming mismatch to be aware of:** `append_row()` writes the header as `"{Member} Rating"` (e.g. `"Garrett Rating"`), but the in-code dict keys throughout use `rating_{Member}` (e.g. `rating_Garrett`, matching the modal's `block_id`s). `get_all_rows()` reconstructs each row as a dict keyed by whatever's in row 1 of the sheet — so those dicts use the `"Garrett Rating"`-style keys, while `append_row()`'s input `data` dict uses `rating_Garrett`-style keys. Both `show_stats()` and `show_history()` correctly read with `f"{m} Rating"` to match the sheet header, so this isn't currently a bug — but if you rename anything, keep both conventions in mind since they aren't unified into one constant anywhere.

## Editing the sheet by hand

Since there's no validation on write, it's fine to fix typos or delete a bad row directly in Google Sheets. Just make sure:
- The header row stays exactly as the bot wrote it (column names are matched by exact string).
- `Paid By` values stay exactly `Garrett`, `Greg`, or `Ian` (case-sensitive) — otherwise `get_next_payer()` will reset to Garrett.
