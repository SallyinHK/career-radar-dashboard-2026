# Job Fit Radar

A local, low-code job monitoring workflow for personal job search.

It monitors selected company career pages / ATS boards, compares each role with your CV/background, scores fit from 0-100, and sends high-match roles as phone/computer notifications.

## What this MVP does

- Supports Greenhouse job boards
- Supports Lever job boards
- Supports Ashby job boards
- Supports simple public career pages as a fallback
- Scores jobs using either:
  - rules only, no paid AI API needed, or
  - OpenAI API, or
  - Gemini API
- Stores jobs in SQLite so duplicates are avoided
- Sends roles scoring above your threshold through one of these channels:
  - ntfy, recommended if Telegram registration asks for SMS fee
  - Telegram
  - Discord webhook
- Runs once or every 12 hours

## What this MVP intentionally does not do

It does not directly scrape LinkedIn / JobsDB / Indeed. Those platforms have restrictions on automated scraping/access, so the portfolio-safe version monitors official career pages and public ATS sources first.

## Setup in Cursor

### 1. Open the folder

Unzip this project and open the `job-fit-radar` folder in Cursor.

### 2. Create your `.env` file

Copy `.env.example` and rename the copy to `.env`.

If Telegram registration asks you to pay an SMS fee, use ntfy first:

```env
AI_PROVIDER=rules
NOTIFIER=ntfy
NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=job-fit-radar-change-this-to-a-long-random-name
DATABASE_PATH=jobs.db
```

Important: for `NTFY_TOPIC`, use a long random topic name, for example `job-fit-radar-sally-2026-x8p2kq91`. Public ntfy.sh topics are not private if someone guesses the topic name.

You can start with `AI_PROVIDER=rules` first. After the workflow runs, switch to `openai` or `gemini` for better judgement.

### 3. Install packages

In Cursor Terminal:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4A. Recommended notification option: ntfy

This avoids Telegram SMS verification entirely.

1. Install the ntfy app on your phone, or open `https://ntfy.sh` in a browser.
2. Subscribe to the same topic you put in `.env`, for example:

```text
job-fit-radar-sally-2026-x8p2kq91
```

3. In Cursor Terminal, run:

```bash
python main.py send-test
```

You should receive a test push notification.

### 4B. Optional notification option: Telegram

Only use this if you already have a working Telegram account.

In `.env`:

```env
NOTIFIER=telegram
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Then:

1. Open Telegram and search `@BotFather`.
2. Send `/newbot`.
3. Follow the instructions and copy the bot token.
4. Put the token into `.env` as `TELEGRAM_BOT_TOKEN`.
5. Open your new bot and send `/start`.
6. In Cursor Terminal, run:

```bash
python main.py get-chat-id
```

Look for `chat -> id`, then put that number into `.env` as `TELEGRAM_CHAT_ID`.

Test:

```bash
python main.py send-test
```

### 4C. Optional notification option: Discord

In `.env`:

```env
NOTIFIER=discord
DISCORD_WEBHOOK_URL=your_discord_webhook_url
```

Then run:

```bash
python main.py send-test
```

### 5. Add job sources

Open `sources.yaml`. Enable at least one source.

Greenhouse example:

```yaml
sources:
  - name: Company Name
    type: greenhouse
    board_token: companytoken
    enabled: true
```

If the job board URL is:

```text
https://boards.greenhouse.io/companytoken
```

then `board_token` is:

```text
companytoken
```

Lever example:

```yaml
sources:
  - name: Company Name
    type: lever
    company_slug: companyslug
    enabled: true
```

If the job board URL is:

```text
https://jobs.lever.co/companyslug
```

then `company_slug` is:

```text
companyslug
```

Ashby example:

```yaml
sources:
  - name: Company Name
    type: ashby
    org_slug: companyslug
    enabled: true
```

If the job board URL is:

```text
https://jobs.ashbyhq.com/companyslug
```

then `org_slug` is:

```text
companyslug
```

Generic career page example:

```yaml
sources:
  - name: Company Name
    type: webpage
    url: "https://company.com/careers"
    enabled: true
```

Generic webpages are less accurate than Greenhouse/Lever/Ashby.

### 6. Run once

```bash
python main.py scan-once
```

### 7. Run every 2 hours

```bash
python main.py run-forever
```

Leave the terminal open. It will scan every 2 hours based on `config.yaml`.

## Optional: use AI scoring

### OpenAI

In `.env`:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

### Gemini

In `.env`:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

## Adjust your matching profile

Edit `profile.md` to update your CV, target roles, visa constraints, and language constraints.

This is the main file controlling how the AI thinks about your fit.

## Adjust threshold and frequency

Open `config.yaml`:

```yaml
run:
  interval_hours: 2
  score_threshold: 80
```

Change `score_threshold` to 75 if you want more opportunities.

## Useful commands

```bash
python main.py init-db       # initialize database
python main.py scan-once     # scan once and send alerts
python main.py run-forever   # scan every interval
python main.py send-test     # send a test notification
python main.py get-chat-id   # Telegram only: get your Telegram chat id
python main.py recent        # show recent jobs in terminal
```

## Suggested portfolio description

I built a local AI-powered Job Fit Radar that monitors selected company career pages and public ATS boards, evaluates each role against my CV, and sends high-match roles every two hours. The workflow scores roles based on role relevance, internship fit, visa feasibility, language requirements, and career value.

## JobsDB / LinkedIn monitoring mode

This version supports `type: search_page` sources for public job-board search result URLs.

- For JobsDB: open JobsDB, search your keywords, sort by newest/listed date, apply any 24h/recent filters, then copy the final URL into `sources.yaml`.
- For LinkedIn: open LinkedIn Jobs, search your keywords, set Date posted = Past 24 hours and Sort by = Most recent, then copy the final URL into `sources.yaml`. The default examples use `f_TPR=r86400` and `sortBy=DD`.

The script does not log in, solve CAPTCHAs, use proxies, or bypass anti-bot systems. If a page blocks normal requests, the source will print a warning and skip it. In that case, keep the search URL as a manual quick-open link or use official company pages/ATS sources.


## Notes for v2 job-board mode

This version uses optional browser rendering for JobsDB/LinkedIn public search pages because some job boards render cards with JavaScript.
After installing requirements, run once:

```bash
python -m playwright install chromium
```

The tool does not log in, solve CAPTCHAs, use proxies, or bypass access controls. If a site blocks access, the source will be skipped or return zero jobs.

If you previously ran an older noisy version, delete the old database before re-scanning:

```bash
rm jobs.db
python main.py scan-once
```


## v3: Concise phone alerts + clickable dashboard

This version keeps ntfy phone alerts short. Each alert shows only the top 3 roles with score, one fit reason, one risk, and the apply link. It also creates a clickable browser dashboard at:

```bash
outputs/latest_shortlist.html
```

Open it with:

```bash
python main.py dashboard
```

Optional AI scoring:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Or:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4-mini
```

The config file includes an AI pre-filter, so the model is called only for roles above `ai.min_rule_score`.
