# Yafri Next

An English/Bengali Telegram companion using Gemini, SQLite conversation history, user-controlled long-term memories, alarms and daily reminders.

## Setup (Windows PowerShell)

1. Create/activate a virtual environment:
   `python -m venv venv`
   `.env\Scripts\Activate.ps1`
2. Install:
   `python -m pip install --upgrade pip`
   `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add BOT_TOKEN and GEMINI_API_KEY.
4. Run `python bot.py`, then send `/start` to the bot.

## Commands

- `/start` — register and activate daily reminders
- `/alarm 6:00 AM` or `/alarm 18:00` — set an alarm
- `/stopalarm` — stop an active alarm
- `/status` — show reminder settings
- `/remember <fact>` — save a user-approved memory
- `/memories` — review saved memories
- `/forget <number>` — delete one saved memory
- `/clear` — clear recent conversation history, not saved memories
- `/help` — help

## Included behaviour

- Conversation history: recent turns are included in each AI request.
- Long-term memory is opt-in via `/remember`; review and delete with `/memories` and `/forget`.
- English and Bengali: Yafri follows the language used by the user.
- Image questions: send a photo with an optional caption.
- Daily check-ins: lunch at 13:00; sleep at 22:30 and 23:00; no reply by 23:10 triggers the saved alarm time.
- Alarm supports 12-hour and 24-hour formats, a STOP button, text stop phrases and `/stopalarm`.
- SQLite stores alarms, history and memories. Scheduled jobs are restored after process restart.

## Important deployment/privacy notes

- The free Gemini API tier has model and rate limits; availability can change. Check the official Gemini pricing page.
- Google's free tier states that submitted content may be used to improve its products. Do not send passwords, private documents or sensitive information.
- Free API use does not provide a free always-on server. Hosting must separately support a continuously running worker.
- Use persistent disk storage for `bot_data.db`; otherwise data can be lost on redeploy/restart.
- Run exactly one polling worker per bot token.
- Telegram notifications are not a native phone alarm and depend on network, Telegram notification settings and the host process being online.
