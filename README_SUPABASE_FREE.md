# MetaVerse SquadFinder — Supabase Free Cloud Edition

This package moves SquadFinder's persistent data from local SQLite to a Supabase
Postgres project. Supabase provides the database; the included `render.yaml`
hosts the Python/Flask web process on Render's free web-service tier.

## Why two services?

Supabase provides Postgres, Auth, Realtime, Storage, and Edge Functions, but it
does not run an arbitrary long-lived Python Flask server. The current SquadFinder
is a Flask application, so a small Python host is still required. This package
uses:

- **Supabase Free:** permanent Postgres data for users, maps, squads, messages,
  friends, reviews, events, notifications, and WebRTC signaling.
- **Render Free:** runs the Flask website at a public trusted-HTTPS URL.

## 1. Create the Supabase project

1. Create a free Supabase project.
2. Wait until the database is ready.
3. Open **Connect** and select the **Session pooler** connection string.
4. Replace the password placeholder with the database password you chose.
5. Keep this connection string secret. Do not paste the Supabase service-role key
   into browser JavaScript.

The Session pooler is recommended for free hosting and IPv4-compatible app hosts.

## 2. Prepare and optionally migrate your current app

On Windows, double-click `PREPARE_SUPABASE_WINDOWS.bat`.

Use a new, empty Supabase project for the first migration.

The wizard will:

- test the encrypted Supabase connection;
- save local secrets in `.env` (excluded from Git);
- optionally import `instance/squadfinder.db` while preserving IDs, real accounts,
  password hashes, rooms, chat, friends, reviews, and events;
- optionally remove the bundled fake users, fake rooms, and fictional sample maps.

To run the migration manually:

```bash
python scripts/migrate_sqlite_to_supabase.py --sqlite instance/squadfinder.db --clean-demo
```

## 3. Publish the Flask app for free

1. Put this folder in a private GitHub repository. Do not upload `.env` or the
   `instance` folder.
2. In Render, choose **New > Blueprint** and select that repository.
3. Render reads `render.yaml` and creates the free web service.
4. In the requested environment variables, paste:
   - `SUPABASE_DB_URL`: your Supabase **Session pooler** connection string;
   - `SQUADFINDER_ADMIN_USERNAME`;
   - `SQUADFINDER_ADMIN_EMAIL`;
   - `SQUADFINDER_ADMIN_PASSWORD`.
5. Deploy. After the first successful login, remove
   `SQUADFINDER_ADMIN_PASSWORD` from Render so it is not retained unnecessarily.

Render automatically provides trusted HTTPS, so browsers no longer show the
local self-signed-certificate warning.

## Public launch defaults

- Fake demo accounts and fake live rooms are disabled.
- The fictional bundled catalog is disabled.
- Import your existing database, or let users add real in-game maps through
  **Add Real Map**.
- Set `SQUADFINDER_SEED_CATALOG=1` only for a clearly-labelled test site.

## Voice chat

HTTPS and browser microphone access work on the public Render URL. WebRTC uses
public STUN servers. Some users on restrictive mobile or corporate networks will
need a TURN server; configure the optional TURN environment variables shown in
`.env.example`.

## Free-plan behavior

Free hosting is suitable for an MVP. Render may spin the web process down during
inactivity, so the first visit after a quiet period can take longer. Supabase free
projects have usage limits and may be paused according to the current free-plan
policies. Upgrade only when real traffic requires it.

## Local test using Supabase

After the wizard creates `.env`:

```bash
python -m pip install -r requirements.txt
python -c "from dotenv import load_dotenv; load_dotenv(); import app; app.app.run(port=5000)"
```

Open `http://127.0.0.1:5000` for a local test. The published Render URL uses HTTPS.
