# MetaVerse SquadFinder

SquadFinder is a Flask application for finding players, creating squads, discovering maps, chatting with room members, following creators, joining events, and using browser-based WebRTC voice chat.

This repository contains the **source code**. Anyone who downloads or clones it can connect it to **their own Supabase project** and run their own copy of SquadFinder.

## What you need

Before running SquadFinder, install:

- **Python 3.13**
- A free **Supabase** account
- Git is optional. You can also download the repository as a ZIP from GitHub.

## 1. Download SquadFinder

Either clone the repository:

```bash
git clone https://github.com/Jad-Programmer/SquadFinder.git
cd SquadFinder
```

or use **Code > Download ZIP** on GitHub and extract it.

## 2. Create your own Supabase project

1. Go to Supabase and create a new project.
2. Choose a database password and keep it safe.
3. Wait until the project finishes creating the database.
4. Open the Supabase **SQL Editor**.
5. Open `schema_postgres.sql` from this repository, copy its contents, paste them into the SQL Editor, and run it.
6. In Supabase, open **Connect** and choose the **Session pooler** connection string.
7. Replace the password placeholder in that connection string with your own database password.

Your connection string will look similar to:

```text
postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
```

Keep this URL private. **Never post your real Supabase database password or connection string on GitHub.**

## 3. Create your `.env` file

In the SquadFinder folder, make a copy of `.env.example` and name it:

```text
.env
```

Then edit `.env` and replace the placeholders with your own information.

The most important setting is:

```env
SUPABASE_DB_URL=YOUR_SUPABASE_SESSION_POOLER_URL
```

You can also set your first administrator account:

```env
SQUADFINDER_ADMIN_USERNAME=admin
SQUADFINDER_ADMIN_EMAIL=you@example.com
SQUADFINDER_ADMIN_PASSWORD=choose-a-strong-password
```

`SQUADFINDER_SECRET_KEY` should be a long random value. Do not share it publicly.

The `.env` file is already ignored by Git, so your private values should not be committed to the repository.

## 4. Install the Python packages

Open Command Prompt, PowerShell, or a terminal inside the SquadFinder folder and run:

```bash
python -m pip install -r requirements.txt
```

## 5. Run SquadFinder

Run:

```bash
python -c "from app import app; app.run(host='127.0.0.1', port=5000)"
```

Then open:

```text
http://127.0.0.1:5000
```

You should now see SquadFinder running with your own Supabase database.

## First launch

On the first launch, SquadFinder creates any required application data and uses the Supabase connection from your `.env` file.

If you configured the optional administrator variables, use that administrator account to sign in.

For security, after confirming that the administrator account was created successfully, you can remove `SQUADFINDER_ADMIN_PASSWORD` from your `.env` file.

## Run without Supabase

SquadFinder can also use a local SQLite database when no Supabase/Postgres database URL is configured. This is useful for local development or testing.

The local database is stored inside:

```text
instance/squadfinder.db
```

For a shared or online installation, Supabase/Postgres is recommended instead of SQLite.

## Put your own copy online

If you want other people to access your SquadFinder installation over the internet, you need a Python host in addition to Supabase.

This repository includes `render.yaml` for deployment on Render.

A typical setup is:

- **GitHub** — stores your SquadFinder source code
- **Supabase** — stores users, maps, squads, messages, friends, reviews, events, notifications, and other persistent data
- **Render** — runs the Flask application and gives it a public HTTPS address

When deploying, add your private environment variables directly in the hosting provider. Do **not** put your real `.env` file in GitHub.

## Voice chat

SquadFinder includes browser-based WebRTC voice chat.

For public internet deployments, HTTPS is required for normal microphone access. Public STUN servers work for many users, but users behind restrictive networks may require a TURN server. Optional TURN settings are listed in `.env.example`.

## Important security notes

- Never commit `.env`.
- Never publish your Supabase database password.
- Never publish your full `SUPABASE_DB_URL`.
- Do not put Supabase service-role keys in browser JavaScript.
- Use a strong administrator password.
- Use HTTPS when exposing SquadFinder publicly.

## Main project files

```text
app.py                  Main Flask application
catalog.py              Supported game/platform catalog
schema_postgres.sql     Supabase/Postgres database schema
requirements.txt        Python dependencies
.env.example            Safe configuration example
render.yaml             Optional Render deployment configuration
wsgi.py                 Production WSGI entry point
templates/              HTML pages
static/                 CSS, JavaScript, and platform logos
```

## Quick start summary

```text
1. Download SquadFinder
2. Create a Supabase project
3. Run schema_postgres.sql in Supabase SQL Editor
4. Copy the Session pooler database URL
5. Copy .env.example to .env
6. Put your own Supabase URL in .env
7. Run: python -m pip install -r requirements.txt
8. Run SquadFinder
9. Open http://127.0.0.1:5000
```

Each person who uses this source code should create and use **their own Supabase project and private credentials**.
