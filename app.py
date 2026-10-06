from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # SQLite-only local installs do not need the PostgreSQL driver.
    psycopg = None
    dict_row = None
    ConnectionPool = None

from catalog import DEMO_MAPS, PLATFORMS, PLATFORM_SHORT

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DATABASE = INSTANCE_DIR / "squadfinder.db"
SECRET_FILE = INSTANCE_DIR / ".secret_key"


def normalize_database_url(value: str) -> str:
    """Return a psycopg-compatible URL and require TLS for hosted Postgres."""
    value = (value or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    if not value:
        return ""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if host not in {"localhost", "127.0.0.1", "::1"}:
        query.setdefault("sslmode", "require")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


DATABASE_URL = normalize_database_url(
    os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL") or ""
)
USE_POSTGRES = DATABASE_URL.startswith(("postgresql://", "postgres://"))
CLOUD_MODE = os.environ.get("SQUADFINDER_CLOUD", "1" if USE_POSTGRES else "0") == "1"
USE_HTTPS = os.environ.get("SQUADFINDER_HTTPS") == "1"
FORCE_HTTPS = os.environ.get("SQUADFINDER_FORCE_HTTPS") == "1"
SEED_DEMO = os.environ.get("SQUADFINDER_SEED_DEMO", "0" if CLOUD_MODE else "1") == "1"
SEED_CATALOG = os.environ.get("SQUADFINDER_SEED_CATALOG", "0" if CLOUD_MODE else "1") == "1"

if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
    TRUSTED_HTTPS_DIR = Path(os.environ["LOCALAPPDATA"]) / "MetaVerseSquadFinder" / "trusted_https"
else:
    TRUSTED_HTTPS_DIR = INSTANCE_DIR / "trusted_https"


def load_or_create_secret_key() -> str:
    configured = os.environ.get("SQUADFINDER_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if configured:
        return configured
    if SECRET_FILE.exists():
        stored = SECRET_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    generated = secrets.token_hex(32)
    SECRET_FILE.write_text(generated, encoding="utf-8")
    return generated


app = Flask(__name__, instance_path=str(INSTANCE_DIR))
if CLOUD_MODE:
    # Render/Vercel/other HTTPS proxies terminate TLS before forwarding to Flask.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
app.config.update(
    SECRET_KEY=load_or_create_secret_key(),
    DATABASE=str(DATABASE),
    DATABASE_URL=DATABASE_URL,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=bool(CLOUD_MODE or USE_HTTPS),
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    PREFERRED_URL_SCHEME="https" if CLOUD_MODE else "http",
)


PLAY_STYLES = ["Casual", "Competitive", "Grinding", "Learning", "Speedrun", "Playtest"]
REGIONS = ["Auto", "Europe", "Middle East", "North America East", "North America West", "Asia", "Oceania", "South America"]
LANGUAGES = ["English", "Arabic", "French", "Spanish", "German", "Portuguese", "Turkish"]
MIC_OPTIONS = ["Optional", "Required", "No microphone"]
VOICE_MAX_PARTICIPANTS = 8

MAP_REFERENCE_HELP = {
    "Fortnite Creative": "Enter the 12-digit island code shown in Fortnite, for example 1234-5678-9012.",
    "Roblox": "Paste the Roblox experience URL or its numeric experience/place ID.",
    "Minecraft": "Enter the server address, Realm invite code, or exact world/map reference shared by the host.",
    "GTA V FiveM": "Paste the cfx.re/join code or the exact server address shown by FiveM.",
    "Halo Infinite Forge": "Paste the published Forge map URL, asset ID, or exact in-game reference.",
    "Fall Guys Creative": "Enter the share code exactly as Fall Guys displays it.",
    "Rec Room": "Enter the public room name, room URL, or exact room reference.",
    "VRChat": "Paste the world ID beginning with wrld_ or the public world URL.",
    "Core Games": "Paste the public Core game URL or exact game ID.",
    "Garry's Mod": "Enter the server address, Steam Workshop URL, or numeric Workshop ID.",
    "Counter-Strike 2 Workshop": "Paste the Steam Workshop URL or numeric Workshop ID.",
    "Trackmania": "Paste the map UID, public map URL, or exact in-game map reference.",
}

PLACEHOLDER_REFERENCE_WORDS = ("demo", "example", "sample", "fake", ".test", "localhost")
_cleanup_lock = threading.Lock()
_last_cleanup_monotonic = 0.0


def platform_slug(value: str) -> str:
    cleaned = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())
    return cleaned or "custom"


def validate_map_reference(platform: str, value: str) -> tuple[str, str | None]:
    """Normalize and validate a user-supplied in-game map reference.

    This checks obvious formatting mistakes and placeholders. It does not claim
    that the map exists on the platform; API verification can be added later.
    """
    reference = " ".join((value or "").strip().split())
    if len(reference) < 3:
        return reference, "Enter the real map code, ID, URL, or server address shown in the game."
    if len(reference) > 180:
        return reference, "The map reference is too long."
    lowered = reference.lower()
    if any(word in lowered for word in PLACEHOLDER_REFERENCE_WORDS):
        return reference, "Placeholder or demo codes are not allowed. Enter the real in-game map reference."

    if platform == "Fortnite Creative" and not re.fullmatch(r"\d{4}-\d{4}-\d{4}", reference):
        return reference, "Fortnite island codes must use the format 1234-5678-9012."
    if platform == "Roblox":
        is_numeric = bool(re.fullmatch(r"\d{5,20}", reference))
        is_url = bool(re.match(r"https?://(?:www\.)?roblox\.com/", reference, re.I))
        if not (is_numeric or is_url):
            return reference, "Paste a Roblox experience URL or numeric experience/place ID."
    if platform == "VRChat" and not (reference.startswith("wrld_") or "vrchat.com/home/world/" in lowered):
        return reference, "Paste the VRChat world ID beginning with wrld_ or its public world URL."
    if platform == "Counter-Strike 2 Workshop":
        is_numeric = bool(re.fullmatch(r"\d{6,20}", reference))
        is_url = "steamcommunity.com/sharedfiles/filedetails" in lowered or "steamcommunity.com/workshop/filedetails" in lowered
        if not (is_numeric or is_url):
            return reference, "Paste the numeric Steam Workshop ID or the Workshop page URL."

    return reference, None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def time_ago(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return "recently"
    seconds = max(0, int((utcnow() - dt).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def time_left(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return "expired"
    seconds = int((dt - utcnow()).total_seconds())
    if seconds <= 0:
        return "expired"
    minutes = max(1, seconds // 60)
    if minutes < 60:
        return f"{minutes}m left"
    hours = minutes // 60
    return f"{hours}h left"


def event_time(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return "Date unavailable"
    return dt.astimezone().strftime("%a, %d %b · %I:%M %p").replace(" 0", " ")


app.jinja_env.filters["timeago"] = time_ago
app.jinja_env.filters["timeleft"] = time_left
app.jinja_env.filters["eventtime"] = event_time


POSTGRES_ID_TABLES = {
    "users", "maps", "rooms", "guides", "room_messages", "voice_signals",
    "notifications", "activity_items", "gaming_events",
}
POSTGRES_POOL = None


def get_postgres_pool():
    global POSTGRES_POOL
    if not USE_POSTGRES:
        return None
    if psycopg is None or ConnectionPool is None:
        raise RuntimeError(
            "PostgreSQL support is not installed. Run: pip install -r requirements.txt"
        )
    if POSTGRES_POOL is None:
        POSTGRES_POOL = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=0,
            max_size=max(2, int(os.environ.get("SQUADFINDER_DB_POOL_SIZE", "5"))),
            timeout=20,
            kwargs={"autocommit": False, "row_factory": dict_row},
            open=True,
        )
    return POSTGRES_POOL


def postgres_sql(sql: str) -> str:
    """Translate the small SQLite SQL subset used by SquadFinder to Postgres."""
    translated = sql
    ignore_conflict = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", translated, re.I))
    translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", translated, flags=re.I)
    translated = translated.replace("COLLATE NOCASE", "")
    translated = translated.replace("MAX(1,current_members-1)", "GREATEST(1,current_members-1)")
    translated = translated.replace("MAX(1, current_members-1)", "GREATEST(1, current_members-1)")
    translated = re.sub(r"\bLIKE\b", "ILIKE", translated, flags=re.I)
    translated = translated.replace("?", "%s")
    # SQLite supports two-argument MIN/MAX as scalar functions. Postgres names
    # their scalar equivalents LEAST/GREATEST.
    translated = re.sub(r"\bMIN\(([^,()]+),\s*(%s)\)", r"LEAST(\1, \2)", translated, flags=re.I)
    translated = re.sub(r"\bMAX\(([^,()]+),\s*(%s)\)", r"GREATEST(\1, \2)", translated, flags=re.I)
    if ignore_conflict and "ON CONFLICT" not in translated.upper():
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return translated


def inserted_table(sql: str) -> str | None:
    match = re.match(r"\s*INSERT(?:\s+OR\s+IGNORE)?\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.I)
    return match.group(1).lower() if match else None


@contextmanager
def db_cursor(commit: bool = False):
    """Compatibility context manager for the local SQLite edition."""
    if USE_POSTGRES:
        pool = get_postgres_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                try:
                    yield cur
                    if commit:
                        conn.commit()
                    else:
                        conn.rollback()
                except Exception:
                    conn.rollback()
                    raise
        return

    conn = sqlite3.connect(app.config["DATABASE"], timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=8000")
    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    finally:
        conn.close()


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    if USE_POSTGRES:
        pool = get_postgres_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(postgres_sql(sql), params)
                rows = cur.fetchall()
            conn.rollback()
        return rows
    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple[Any, ...] = ()) -> Any | None:
    if USE_POSTGRES:
        pool = get_postgres_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(postgres_sql(sql), params)
                row = cur.fetchone()
            conn.rollback()
        return row
    with db_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    if USE_POSTGRES:
        pool = get_postgres_pool()
        statement = postgres_sql(sql)
        table = inserted_table(sql)
        wants_id = table in POSTGRES_ID_TABLES and "RETURNING" not in statement.upper()
        if wants_id:
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
        with pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(statement, params)
                    inserted_id = int(cur.fetchone()["id"]) if wants_id else 0
                conn.commit()
                return inserted_id
            except Exception:
                conn.rollback()
                raise
    with db_cursor(commit=True) as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def execute_script_postgres(schema: str) -> None:
    statements = [part.strip() for part in schema.split(";") if part.strip()]
    pool = get_postgres_pool()
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def bootstrap_cloud_admin() -> None:
    username = os.environ.get("SQUADFINDER_ADMIN_USERNAME", "").strip()
    email = os.environ.get("SQUADFINDER_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("SQUADFINDER_ADMIN_PASSWORD", "")
    if not (username and email and password):
        return
    existing = query_one(
        "SELECT id FROM users WHERE lower(username)=? OR lower(email)=?",
        (username.lower(), email),
    )
    if existing:
        execute(
            "UPDATE users SET is_creator=1,is_admin=1 WHERE id=?",
            (existing["id"],),
        )
        return
    execute(
        """INSERT INTO users
        (username,email,password_hash,display_name,platform_handle,region,language,bio,is_creator,is_admin,created_at)
        VALUES (?,?,?,?,?,'Auto','English','Cloud administrator',1,1,?)""",
        (username, email, generate_password_hash(password), username, username, iso(utcnow())),
    )


def init_db() -> None:
    if USE_POSTGRES:
        schema = (BASE_DIR / "schema_postgres.sql").read_text(encoding="utf-8")
        execute_script_postgres(schema)
    else:
        schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
        conn = sqlite3.connect(app.config["DATABASE"], timeout=8)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=8000")
            conn.executescript(schema)
            conn.commit()
        finally:
            conn.close()
    bootstrap_cloud_admin()
    seed_db()


def seed_db() -> None:
    """Create demo accounts and add any missing built-in catalog entries.

    The map insertion is intentionally additive: upgrading the app keeps an
    existing SQLite database and adds newly shipped games/maps without
    overwriting creator edits or user-created maps.
    """
    now = utcnow()

    # Public cloud deployments start clean by default. Existing SQLite data can
    # be imported with scripts/migrate_sqlite_to_supabase.py. Set
    # SQUADFINDER_SEED_CATALOG=1 only when you intentionally want the bundled
    # sample catalog; it is labelled Sample and is not represented as verified.
    if not SEED_DEMO:
        if SEED_CATALOG:
            for spec in DEMO_MAPS:
                key = (spec["platform"], spec["code"])
                if query_one("SELECT id FROM maps WHERE platform=? AND map_code=?", key):
                    continue
                execute(
                    """INSERT INTO maps
                    (name,platform,map_code,description,genre,max_party,session_minutes,difficulty,
                     active_players,verified,creator_id,badge,version,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,0,0,NULL,'Sample',?,?)""",
                    (
                        spec["name"], spec["platform"], spec["code"],
                        "Sample catalog entry — replace with a real published in-game map before launch.",
                        spec["genre"], spec["party"], spec["minutes"], spec["difficulty"],
                        spec["version"], iso(now),
                    ),
                )
        return

    def ensure_user(
        username: str,
        email: str,
        password: str,
        display_name: str,
        platform_handle: str,
        region: str,
        language: str,
        bio: str,
        is_creator: int = 0,
        is_admin: int = 0,
    ) -> int:
        existing = query_one("SELECT id FROM users WHERE lower(username)=? OR lower(email)=?", (username.lower(), email.lower()))
        if existing:
            return int(existing["id"])
        return execute(
            """INSERT INTO users
            (username,email,password_hash,display_name,platform_handle,region,language,bio,is_creator,is_admin,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                username,
                email,
                generate_password_hash(password),
                display_name,
                platform_handle,
                region,
                language,
                bio,
                is_creator,
                is_admin,
                iso(now - timedelta(days=14)),
            ),
        )

    demo_id = ensure_user(
        "demo", "demo@metasquad.local", "demo123", "NovaRunner", "NovaRunner_7",
        "Europe", "English", "Co-op fan. I like clear objectives and friendly squads."
    )
    creator_id = ensure_user(
        "creator", "creator@metasquad.local", "creator123", "MapSmith", "MapSmithStudio",
        "North America East", "English", "UGC creator building social co-op maps.", 1, 0
    )
    admin_id = ensure_user(
        "admin", "admin@metasquad.local", "admin123", "SquadFinder Admin", "MetaVerseHQ",
        "Europe", "English", "Platform administrator.", 1, 1
    )

    # Add the full built-in catalog while preserving existing rows and edits.
    map_lookup: dict[tuple[str, str], int] = {}
    for spec in DEMO_MAPS:
        key = (spec["platform"], spec["code"])
        existing = query_one("SELECT id FROM maps WHERE platform=? AND map_code=?", key)
        if existing:
            map_lookup[key] = int(existing["id"])
            continue
        owner_id = creator_id if spec["owner"] == "creator" else admin_id
        map_lookup[key] = execute(
            """INSERT INTO maps
            (name,platform,map_code,description,genre,max_party,session_minutes,difficulty,
             active_players,verified,creator_id,badge,version,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                spec["name"], spec["platform"], spec["code"], spec["description"],
                spec["genre"], spec["party"], spec["minutes"], spec["difficulty"],
                spec["active"], spec["verified"], owner_id, spec["badge"],
                spec["version"], iso(now - timedelta(hours=spec["hours"])),
            ),
        )

    demo_users = [
        ("luna", "LunaByte", "LunaByte", "Middle East", "Arabic", "Puzzle player and patient teammate."),
        ("kai", "KaiZero", "KaiZeroLive", "Europe", "English", "Competitive but chill."),
        ("mira", "MiraCraft", "MiraCrafts", "Europe", "French", "Minecraft builder and event host."),
        ("rex", "RexRush", "RexRush88", "North America East", "English", "Speedruns, raids, and boss fights."),
        ("aria", "AriaVR", "AriaVRChat", "Middle East", "English", "Social VR events and puzzle rooms."),
        ("mason", "MasonForge", "MasonForge", "North America West", "English", "Forge campaigns and custom PvP."),
    ]
    extra_ids: list[int] = []
    for username, display, handle, region, language, bio in demo_users:
        extra_ids.append(
            ensure_user(
                username,
                f"{username}@metasquad.local",
                "demo123",
                display,
                handle,
                region,
                language,
                bio,
            )
        )

    # Seed active-looking rooms only on a brand-new room database. User rooms are
    # never replaced or duplicated during upgrades.
    if not query_one("SELECT id FROM rooms LIMIT 1"):
        room_data = [
            (("Fortnite Creative", "4821-7390-1158"), extra_ids[0], "Vault run — learning the laser route", "Learning", "Middle East", "Arabic", "Optional", 4, 2, "Need patient players. We will explain the switch order.", 95),
            (("Fortnite Creative", "9130-2244-6712"), extra_ids[1], "Ranked warm-up squad", "Competitive", "Europe", "English", "Required", 6, 4, "Good comms, no toxicity. Playing three rounds.", 80),
            (("Minecraft", "play.blockharbor.test"), extra_ids[2], "Island boss + puzzle night", "Casual", "Europe", "French", "Optional", 6, 3, "New players welcome. Bring food and basic gear.", 120),
            (("Roblox", "18732209114"), extra_ids[3], "Wave 20 achievement grind", "Grinding", "North America East", "English", "Required", 5, 2, "Looking for healer and repair role.", 110),
            (("Halo Infinite Forge", "HI-BBA-7021"), extra_ids[5], "Boarding Action campaign run", "Learning", "North America West", "English", "Required", 4, 2, "First clear; checkpoints and callouts included.", 130),
            (("Fall Guys Creative", "FG-1184-5520"), demo_id, "Hexa Harbor party", "Casual", "Europe", "English", "Optional", 8, 3, "Quick rounds. New players welcome.", 75),
            (("GTA V FiveM", "vaultbreak.test"), creator_id, "Vaultbreak specialist crew", "Competitive", "North America East", "English", "Required", 6, 3, "Need driver, hacker, and crowd-control roles.", 140),
            (("Rec Room", "RR-CLOCKWORK-27"), extra_ids[4], "Clockwork escape clues", "Learning", "Middle East", "English", "Optional", 4, 2, "No spoilers; we solve each room together.", 105),
            (("VRChat", "wrld_orbital_mystery_demo"), extra_ids[4], "Orbital Mystery social lobby", "Casual", "Europe", "English", "Required", 10, 5, "Friendly moderated lobby with two rounds.", 90),
            (("Counter-Strike 2 Workshop", "CS2-WS-RETAKE-18"), extra_ids[1], "Mirage retake practice", "Competitive", "Europe", "English", "Required", 10, 6, "Utility practice and balanced team swaps.", 85),
            (("Trackmania", "TM-TECHSCHOOL-101"), admin_id, "Beginner tech coaching", "Learning", "Auto", "English", "Optional", 8, 3, "Practice drifts and gears with route explanations.", 125),
            (("Core Games", "CORE-OMEGA-772"), creator_id, "Omega night-ten defense", "Grinding", "North America East", "English", "Optional", 6, 2, "Building a balanced resource and defense team.", 115),
        ]
        all_member_ids = extra_ids + [creator_id, admin_id, demo_id]
        for map_key, host_id, title, style, region, language, mic, party_size, current, note, expiry in room_data:
            map_id = map_lookup.get(map_key)
            if not map_id:
                continue
            room_id = execute(
                """INSERT INTO rooms
                (map_id,host_id,title,play_style,region,language,mic,party_size,current_members,note,status,created_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?, 'open', ?,?)""",
                (
                    map_id, host_id, title, style, region, language, mic, party_size,
                    current, note, iso(now - timedelta(minutes=10)),
                    iso(now + timedelta(minutes=expiry)),
                ),
            )
            execute(
                "INSERT INTO room_members (room_id,user_id,joined_at) VALUES (?,?,?)",
                (room_id, host_id, iso(now - timedelta(minutes=10))),
            )
            candidates = [uid for uid in all_member_ids if uid != host_id]
            for uid in candidates[: max(0, current - 1)]:
                execute(
                    "INSERT OR IGNORE INTO room_members (room_id,user_id,joined_at) VALUES (?,?,?)",
                    (room_id, uid, iso(now - timedelta(minutes=6))),
                )

    if not query_one("SELECT id FROM guides LIMIT 1"):
        guide_specs = [
            (("Fortnite Creative", "4821-7390-1158"), creator_id, "Clean vault route for four players", "Assign one caller, two switch runners, and one lookout. Trigger the left corridor first; the right corridor alarm becomes easier after the second checkpoint.", "Strategy", 18, 4),
            (("Fortnite Creative", "9130-2244-6712"), extra_ids[1], "Current experimental loadout priorities", "Prioritize mobility first, then a mid-range weapon. Teams that rotate together after each elimination control the center platform more consistently.", "Meta", 31, 7),
            (("Minecraft", "play.blockharbor.test"), extra_ids[2], "Beginner checklist before Island Trial 3", "Carry food, one water bucket, blocks, and at least one ranged weapon per pair. Set roles before entering because the arena gate locks behind the team.", "Beginner", 12, 24),
            (("Roblox", "18732209114"), extra_ids[3], "Wave 20 team composition", "A reliable group uses two damage roles, one repair role, one support role, and one flexible player. Save area abilities for the double-spawn warning.", "Build", 27, 10),
            (("Halo Infinite Forge", "HI-BBA-7021"), extra_ids[5], "Boarding Action role split", "Use one player on objectives, two clearing lanes, and one carrying power weapons. Regroup before opening each pressure door.", "Strategy", 16, 6),
            (("VRChat", "wrld_orbital_mystery_demo"), extra_ids[4], "Fair lobby settings for ten players", "Use two short discussion windows and keep evidence notes public. Avoid eliminating new players in the first meeting unless there is direct evidence.", "Community", 23, 8),
            (("Counter-Strike 2 Workshop", "CS2-WS-RETAKE-18"), extra_ids[1], "Three-player utility practice", "Rotate one caller, one entry, and one support. Repeat each site until all three players can throw the opening utility without prompts.", "Training", 29, 5),
            (("Trackmania", "TM-TECHSCHOOL-101"), admin_id, "Gear timing before advanced drifts", "Practice clean gear changes at low speed before adding a drift. Consistent exits save more time than aggressive entries on the beginner routes.", "Beginner", 14, 9),
        ]
        for map_key, author_id, title, body, guide_type, helpful, hours in guide_specs:
            map_id = map_lookup.get(map_key)
            if map_id:
                execute(
                    "INSERT INTO guides (map_id,author_id,title,body,guide_type,helpful_count,created_at) VALUES (?,?,?,?,?,?,?)",
                    (map_id, author_id, title, body, guide_type, helpful, iso(now - timedelta(hours=hours))),
                )

    for key in [
        ("Fortnite Creative", "4821-7390-1158"),
        ("Fortnite Creative", "9130-2244-6712"),
        ("Halo Infinite Forge", "HI-BBA-7021"),
    ]:
        map_id = map_lookup.get(key)
        if map_id:
            execute(
                "INSERT OR IGNORE INTO follows (user_id,map_id,created_at) VALUES (?,?,?)",
                (demo_id, map_id, iso(now)),
            )


# Initialize schema and demo data in Flask, Waitress, Gunicorn, or direct-run modes.
init_db()


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["platforms"] = PLATFORMS
app.jinja_env.globals["play_styles"] = PLAY_STYLES
app.jinja_env.globals["regions"] = REGIONS
app.jinja_env.globals["languages"] = LANGUAGES
app.jinja_env.globals["mic_options"] = MIC_OPTIONS
app.jinja_env.globals["platform_short"] = PLATFORM_SHORT
app.jinja_env.globals["platform_slug"] = platform_slug
app.jinja_env.globals["map_reference_help"] = MAP_REFERENCE_HELP


def friend_pair(first_id: int, second_id: int) -> tuple[int, int]:
    return (first_id, second_id) if first_id < second_id else (second_id, first_id)


def friendship_between(first_id: int, second_id: int) -> sqlite3.Row | None:
    low_id, high_id = friend_pair(first_id, second_id)
    return query_one(
        "SELECT * FROM friendships WHERE user_low_id=? AND user_high_id=?",
        (low_id, high_id),
    )


def accepted_friend_ids(user_id: int) -> list[int]:
    rows = query_all(
        """SELECT CASE WHEN user_low_id=? THEN user_high_id ELSE user_low_id END AS friend_id
           FROM friendships
           WHERE status='accepted' AND (user_low_id=? OR user_high_id=?)""",
        (user_id, user_id, user_id),
    )
    return [int(row["friend_id"]) for row in rows]


def notify_user(
    user_id: int,
    actor_id: int | None,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
) -> None:
    if actor_id and user_id == actor_id:
        return
    execute(
        """INSERT INTO notifications
           (user_id,actor_id,kind,title,body,link,is_read,created_at)
           VALUES (?,?,?,?,?,?,0,?)""",
        (user_id, actor_id, kind[:40], title[:120], body[:300], link[:300], iso(utcnow())),
    )


def log_activity(user_id: int, verb: str, detail: str = "", link: str = "") -> None:
    execute(
        "INSERT INTO activity_items (user_id,verb,detail,link,created_at) VALUES (?,?,?,?,?)",
        (user_id, verb[:140], detail[:300], link[:300], iso(utcnow())),
    )


def safe_next(default_endpoint: str, **values: Any) -> str:
    target = request.form.get("next") or request.args.get("next")
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for(default_endpoint, **values)


def parse_local_event_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(timezone.utc)


def event_query(where: str = "", params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return query_all(
        f"""SELECT e.*,m.name AS map_name,m.platform,m.map_code,
                   u.display_name AS host_name,u.username AS host_username,
                   (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id=e.id) AS attendee_count
            FROM gaming_events e
            JOIN maps m ON m.id=e.map_id
            JOIN users u ON u.id=e.host_id
            WHERE e.status='scheduled' {where}
            ORDER BY e.starts_at ASC""",
        params,
    )


@app.before_request
def load_user_and_cleanup() -> None:
    g.user = None
    if session.get("user_id"):
        g.user = query_one("SELECT * FROM users WHERE id=?", (session["user_id"],))
    g.unread_notifications = 0
    if g.user:
        g.unread_notifications = int(query_one(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0",
            (g.user["id"],),
        )["c"])
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not supplied or supplied != session.get("csrf_token"):
            abort(400, "Invalid or missing CSRF token")
    global _last_cleanup_monotonic
    current_monotonic = time.monotonic()
    if current_monotonic - _last_cleanup_monotonic >= 10:
        with _cleanup_lock:
            current_monotonic = time.monotonic()
            if current_monotonic - _last_cleanup_monotonic >= 10:
                now_value = iso(utcnow())
                execute("UPDATE rooms SET status='expired' WHERE status='open' AND expires_at <= ?", (now_value,))
                execute("DELETE FROM voice_presence WHERE last_seen <= ?", (iso(utcnow() - timedelta(seconds=45)),))
                execute("DELETE FROM voice_signals WHERE created_at <= ?", (iso(utcnow() - timedelta(minutes=2)),))
                _last_cleanup_monotonic = current_monotonic


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'; "
        "form-action 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "media-src 'self' blob:"
    )
    # HSTS is opt-in for public-domain deployments. Enabling it on localhost
    # would affect every unrelated localhost app in the user's browser.
    if os.environ.get("SQUADFINDER_HSTS") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Sign in to use squad matching.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def creator_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        if not g.user["is_creator"] and not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def api_error(message: str, status: int):
    return jsonify({"ok": False, "error": message}), status


def get_api_room_member(room_id: int, require_open: bool = False):
    if not g.user:
        return None, api_error("Sign in to use squad communications.", 401)
    room = query_one("SELECT * FROM rooms WHERE id=?", (room_id,))
    if not room:
        return None, api_error("Squad room not found.", 404)
    membership = query_one(
        "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?",
        (room_id, g.user["id"]),
    )
    if not membership and not g.user["is_admin"]:
        return None, api_error("Join this squad before using its chat or voice channel.", 403)
    if require_open and (
        room["status"] != "open"
        or (parse_dt(room["expires_at"]) or utcnow()) <= utcnow()
    ):
        return None, api_error("This squad room is no longer open.", 409)
    return room, None


def get_voice_ice_servers() -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = [{
        "urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]
    }]
    turn_url = os.environ.get("SQUADFINDER_TURN_URL", "").strip()
    if turn_url:
        turn: dict[str, Any] = {"urls": turn_url}
        username = os.environ.get("SQUADFINDER_TURN_USERNAME", "").strip()
        credential = os.environ.get("SQUADFINDER_TURN_CREDENTIAL", "").strip()
        if username:
            turn["username"] = username
        if credential:
            turn["credential"] = credential
        servers.append(turn)
    return servers


def valid_voice_session(value: Any) -> bool:
    if not isinstance(value, str) or not 16 <= len(value) <= 80:
        return False
    return all(ch.isalnum() or ch in "-_" for ch in value)


def get_active_rooms(extra_where: str = "", params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return query_all(
        f"""SELECT r.*, m.name AS map_name, m.platform, m.map_code,
                   u.display_name AS host_name, u.platform_handle AS host_handle,
                   (r.party_size-r.current_members) AS spots_left
            FROM rooms r
            JOIN maps m ON m.id=r.map_id
            JOIN users u ON u.id=r.host_id
            WHERE r.status='open' AND r.expires_at > ? {extra_where}
            ORDER BY r.created_at DESC""",
        (iso(utcnow()),) + params,
    )


@app.route("/")
def home():
    trending = query_all(
        """SELECT m.*, COUNT(DISTINCT r.id) AS room_count
           FROM maps m LEFT JOIN rooms r ON r.map_id=m.id AND r.status='open' AND r.expires_at>?
           GROUP BY m.id ORDER BY m.active_players DESC LIMIT 12""",
        (iso(utcnow()),),
    )
    games = query_all(
        """SELECT platform, COUNT(*) AS map_count, SUM(active_players) AS active_players
           FROM maps GROUP BY platform ORDER BY active_players DESC, platform"""
    )
    rooms = get_active_rooms()[:8]
    upcoming_events = event_query("AND e.starts_at>?", (iso(utcnow()),))[:4]
    stats = {
        "games": query_one("SELECT COUNT(DISTINCT platform) AS c FROM maps")["c"],
        "maps": query_one("SELECT COUNT(*) AS c FROM maps")["c"],
        "rooms": query_one("SELECT COUNT(*) AS c FROM rooms WHERE status='open' AND expires_at>?", (iso(utcnow()),))["c"],
        "players": query_one("SELECT COALESCE(SUM(current_members),0) AS c FROM rooms WHERE status='open' AND expires_at>?", (iso(utcnow()),))["c"],
    }
    return render_template(
        "home.html", trending=trending, games=games, rooms=rooms,
        upcoming_events=upcoming_events, stats=stats,
    )


@app.route("/maps")
def maps_list():
    q = request.args.get("q", "").strip()
    platform = request.args.get("platform", "").strip()
    genre = request.args.get("genre", "").strip()
    sort = request.args.get("sort", "active").strip()
    sort_orders = {
        "active": "m.active_players DESC, m.updated_at DESC",
        "rooms": "room_count DESC, m.active_players DESC",
        "recent": "m.updated_at DESC, m.active_players DESC",
        "name": "LOWER(m.name) ASC",
    }
    if sort not in sort_orders:
        sort = "active"

    sql = """SELECT m.*, COUNT(DISTINCT r.id) AS room_count
             FROM maps m LEFT JOIN rooms r ON r.map_id=m.id AND r.status='open' AND r.expires_at>?
             WHERE 1=1"""
    params: list[Any] = [iso(utcnow())]
    if q:
        sql += " AND (m.name LIKE ? OR m.description LIKE ? OR m.map_code LIKE ? OR m.genre LIKE ? OR m.platform LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like, like])
    if platform:
        sql += " AND m.platform=?"
        params.append(platform)
    if genre:
        sql += " AND m.genre=?"
        params.append(genre)
    sql += f" GROUP BY m.id ORDER BY {sort_orders[sort]}"
    maps = query_all(sql, tuple(params))
    genres = query_all("SELECT DISTINCT genre FROM maps ORDER BY genre")
    game_counts = query_all(
        """SELECT platform, COUNT(*) AS map_count, SUM(active_players) AS active_players
           FROM maps GROUP BY platform ORDER BY active_players DESC, platform"""
    )
    return render_template(
        "maps.html", maps=maps, genres=genres, game_counts=game_counts, q=q,
        selected_platform=platform, selected_genre=genre, selected_sort=sort,
    )


@app.route("/map/<int:map_id>")
def map_detail(map_id: int):
    map_row = query_one(
        """SELECT m.*, u.display_name AS creator_name, u.platform_handle AS creator_handle,
                  (SELECT COUNT(*) FROM follows f WHERE f.map_id=m.id) AS followers
           FROM maps m LEFT JOIN users u ON u.id=m.creator_id WHERE m.id=?""",
        (map_id,),
    )
    if not map_row:
        abort(404)
    rooms = get_active_rooms("AND r.map_id=?", (map_id,))
    guides = query_all(
        """SELECT g.*, u.display_name AS author_name, u.platform_handle AS author_handle
           FROM guides g JOIN users u ON u.id=g.author_id
           WHERE g.map_id=? ORDER BY g.helpful_count DESC, g.created_at DESC""",
        (map_id,),
    )
    reviews = query_all(
        """SELECT mr.*,u.display_name,u.username
           FROM map_reviews mr JOIN users u ON u.id=mr.user_id
           WHERE mr.map_id=? ORDER BY mr.updated_at DESC""",
        (map_id,),
    )
    rating_summary = query_one(
        "SELECT COUNT(*) AS review_count,COALESCE(AVG(rating),0) AS avg_rating FROM map_reviews WHERE map_id=?",
        (map_id,),
    )
    my_review = None
    upcoming_events = event_query("AND e.map_id=? AND e.starts_at>?", (map_id, iso(utcnow())))[:5]
    followed = False
    if g.user:
        followed = bool(query_one("SELECT 1 FROM follows WHERE user_id=? AND map_id=?", (g.user["id"], map_id)))
        my_review = query_one("SELECT * FROM map_reviews WHERE map_id=? AND user_id=?", (map_id, g.user["id"]))
    return render_template(
        "map_detail.html", map=map_row, rooms=rooms, guides=guides, followed=followed,
        reviews=reviews, rating_summary=rating_summary, my_review=my_review,
        upcoming_events=upcoming_events,
    )


@app.route("/rooms")
def rooms_list():
    platform = request.args.get("platform", "")
    style = request.args.get("style", "")
    region = request.args.get("region", "")
    language = request.args.get("language", "")
    clauses: list[str] = []
    params: list[Any] = []
    if platform:
        clauses.append("AND m.platform=?")
        params.append(platform)
    if style:
        clauses.append("AND r.play_style=?")
        params.append(style)
    if region:
        clauses.append("AND r.region=?")
        params.append(region)
    if language:
        clauses.append("AND r.language=?")
        params.append(language)
    rooms = get_active_rooms(" ".join(clauses), tuple(params))
    return render_template("rooms.html", rooms=rooms, selected_platform=platform, selected_style=style, selected_region=region, selected_language=language)


@app.route("/room/<int:room_id>")
def room_detail(room_id: int):
    room = query_one(
        """SELECT r.*, m.name AS map_name,m.platform,m.map_code,m.description AS map_description,
                  u.display_name AS host_name,u.platform_handle AS host_handle,
                  (r.party_size-r.current_members) AS spots_left
           FROM rooms r JOIN maps m ON m.id=r.map_id JOIN users u ON u.id=r.host_id
           WHERE r.id=?""",
        (room_id,),
    )
    if not room:
        abort(404)
    members = query_all(
        """SELECT u.*, rm.joined_at FROM room_members rm JOIN users u ON u.id=rm.user_id
           WHERE rm.room_id=? ORDER BY rm.joined_at""",
        (room_id,),
    )
    joined = bool(g.user and query_one("SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room_id, g.user["id"])))
    message_count = query_one("SELECT COUNT(*) AS c FROM room_messages WHERE room_id=?", (room_id,))["c"]
    return render_template(
        "room_detail.html", room=room, members=members, joined=joined,
        message_count=message_count, voice_ice_servers=get_voice_ice_servers(),
        voice_max_participants=VOICE_MAX_PARTICIPANTS,
    )


@app.route("/rooms/new", methods=["GET", "POST"])
@login_required
def create_room():
    maps = query_all("SELECT id,name,platform,map_code FROM maps ORDER BY active_players DESC")
    preselected = request.args.get("map_id", type=int)
    if request.method == "POST":
        map_id = request.form.get("map_id", type=int)
        title = request.form.get("title", "").strip()
        play_style = request.form.get("play_style", "Casual")
        region = request.form.get("region", "Auto")
        language = request.form.get("language", "English")
        mic = request.form.get("mic", "Optional")
        party_size = request.form.get("party_size", type=int) or 4
        duration = request.form.get("duration", type=int) or 30
        note = request.form.get("note", "").strip()
        if not map_id or not query_one("SELECT id FROM maps WHERE id=?", (map_id,)):
            flash("Choose a valid map.", "error")
        elif len(title) < 4:
            flash("Add a clear room title.", "error")
        elif party_size < 2 or party_size > 20:
            flash("Party size must be between 2 and 20.", "error")
        else:
            room_id = execute(
                """INSERT INTO rooms
                (map_id,host_id,title,play_style,region,language,mic,party_size,current_members,note,status,created_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?,1,?,'open',?,?)""",
                (map_id, g.user["id"], title, play_style, region, language, mic, party_size, note, iso(utcnow()), iso(utcnow() + timedelta(minutes=max(10, min(duration, 180))))),
            )
            execute("INSERT INTO room_members (room_id,user_id,joined_at) VALUES (?,?,?)", (room_id, g.user["id"], iso(utcnow())))
            map_row = query_one("SELECT name FROM maps WHERE id=?", (map_id,))
            log_activity(g.user["id"], "created a live squad room", map_row["name"] if map_row else title, url_for("room_detail", room_id=room_id))
            flash("Your squad room is live.", "success")
            return redirect(url_for("room_detail", room_id=room_id))
    return render_template("create_room.html", maps=maps, preselected=preselected)


@app.post("/room/<int:room_id>/join")
@login_required
def join_room(room_id: int):
    room = query_one("SELECT * FROM rooms WHERE id=?", (room_id,))
    if not room or room["status"] != "open" or (parse_dt(room["expires_at"]) or utcnow()) <= utcnow():
        flash("This room is no longer available.", "error")
        return redirect(url_for("rooms_list"))
    if query_one("SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room_id, g.user["id"])):
        flash("You already joined this room.", "info")
    elif room["current_members"] >= room["party_size"]:
        flash("This squad is already full.", "error")
    else:
        execute("INSERT INTO room_members (room_id,user_id,joined_at) VALUES (?,?,?)", (room_id, g.user["id"], iso(utcnow())))
        execute("UPDATE rooms SET current_members=current_members+1 WHERE id=?", (room_id,))
        notify_user(room["host_id"], g.user["id"], "squad", "A player joined your squad", f"{g.user['display_name']} joined {room['title']}.", url_for("room_detail", room_id=room_id))
        log_activity(g.user["id"], "joined a squad", room["title"], url_for("room_detail", room_id=room_id))
        flash("You joined the squad. Use the platform handles on this page to connect in-game.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.post("/room/<int:room_id>/leave")
@login_required
def leave_room(room_id: int):
    room = query_one("SELECT * FROM rooms WHERE id=?", (room_id,))
    if not room:
        abort(404)
    if room["host_id"] == g.user["id"]:
        flash("Hosts can close a room instead of leaving it.", "info")
    elif query_one("SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room_id, g.user["id"])):
        execute("DELETE FROM room_members WHERE room_id=? AND user_id=?", (room_id, g.user["id"]))
        execute("UPDATE rooms SET current_members=MAX(1,current_members-1) WHERE id=?", (room_id,))
        flash("You left the squad.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.post("/room/<int:room_id>/close")
@login_required
def close_room(room_id: int):
    room = query_one("SELECT * FROM rooms WHERE id=?", (room_id,))
    if not room:
        abort(404)
    if room["host_id"] != g.user["id"] and not g.user["is_admin"]:
        abort(403)
    execute("UPDATE rooms SET status='closed' WHERE id=?", (room_id,))
    flash("Squad room closed.", "success")
    return redirect(url_for("rooms_list"))


@app.route("/quick-match", methods=["GET", "POST"])
@login_required
def quick_match():
    if request.method == "POST":
        platform = request.form.get("platform", "")
        style = request.form.get("play_style", "")
        region = request.form.get("region", "")
        language = request.form.get("language", "")
        clauses = []
        params: list[Any] = []
        if platform:
            clauses.append("AND m.platform=?")
            params.append(platform)
        if style:
            clauses.append("AND r.play_style=?")
            params.append(style)
        if region and region != "Auto":
            clauses.append("AND (r.region=? OR r.region='Auto')")
            params.append(region)
        if language:
            clauses.append("AND r.language=?")
            params.append(language)
        rooms = get_active_rooms(" ".join(clauses), tuple(params))
        rooms = [r for r in rooms if r["current_members"] < r["party_size"] and r["host_id"] != g.user["id"]]
        if rooms:
            return render_template("quick_match.html", match=rooms[0], searched=True)
        return render_template("quick_match.html", match=None, searched=True)
    return render_template("quick_match.html", match=None, searched=False)


@app.post("/map/<int:map_id>/follow")
@login_required
def follow_map(map_id: int):
    if not query_one("SELECT id FROM maps WHERE id=?", (map_id,)):
        abort(404)
    existing = query_one("SELECT 1 FROM follows WHERE user_id=? AND map_id=?", (g.user["id"], map_id))
    if existing:
        execute("DELETE FROM follows WHERE user_id=? AND map_id=?", (g.user["id"], map_id))
        flash("Map removed from your watchlist.", "success")
    else:
        execute("INSERT INTO follows (user_id,map_id,created_at) VALUES (?,?,?)", (g.user["id"], map_id, iso(utcnow())))
        map_row = query_one("SELECT name,creator_id FROM maps WHERE id=?", (map_id,))
        if map_row:
            log_activity(g.user["id"], "followed a map", map_row["name"], url_for("map_detail", map_id=map_id))
            if map_row["creator_id"]:
                notify_user(map_row["creator_id"], g.user["id"], "map", "Your map gained a follower", f"{g.user['display_name']} followed {map_row['name']}.", url_for("map_detail", map_id=map_id))
        flash("Map added to your watchlist.", "success")
    return redirect(url_for("map_detail", map_id=map_id))


@app.route("/map/<int:map_id>/guide/new", methods=["GET", "POST"])
@login_required
def create_guide(map_id: int):
    map_row = query_one("SELECT * FROM maps WHERE id=?", (map_id,))
    if not map_row:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        guide_type = request.form.get("guide_type", "Strategy")
        if len(title) < 5 or len(body) < 20:
            flash("Add a useful title and at least 20 characters of guidance.", "error")
        else:
            execute("INSERT INTO guides (map_id,author_id,title,body,guide_type,helpful_count,created_at) VALUES (?,?,?,?,?,0,?)", (map_id, g.user["id"], title, body, guide_type, iso(utcnow())))
            log_activity(g.user["id"], "published a strategy guide", map_row["name"], url_for("map_detail", map_id=map_id))
            if map_row["creator_id"]:
                notify_user(map_row["creator_id"], g.user["id"], "guide", "New guide on your map", title, url_for("map_detail", map_id=map_id))
            flash("Guide published.", "success")
            return redirect(url_for("map_detail", map_id=map_id))
    return render_template("create_guide.html", map=map_row)


@app.post("/guide/<int:guide_id>/helpful")
@login_required
def helpful_guide(guide_id: int):
    guide = query_one("SELECT * FROM guides WHERE id=?", (guide_id,))
    if not guide:
        abort(404)
    if query_one("SELECT 1 FROM guide_votes WHERE guide_id=? AND user_id=?", (guide_id, g.user["id"])):
        flash("You already marked this guide helpful.", "info")
    else:
        execute("INSERT INTO guide_votes (guide_id,user_id,created_at) VALUES (?,?,?)", (guide_id, g.user["id"], iso(utcnow())))
        execute("UPDATE guides SET helpful_count=helpful_count+1 WHERE id=?", (guide_id,))
        flash("Thanks for the feedback.", "success")
    return redirect(url_for("map_detail", map_id=guide["map_id"]))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        handle = request.form.get("platform_handle", "").strip()
        region = request.form.get("region", "Auto")
        language = request.form.get("language", "English")
        bio = request.form.get("bio", "").strip()[:240]
        if len(display_name) < 2:
            flash("Display name is too short.", "error")
        else:
            execute("UPDATE users SET display_name=?,platform_handle=?,region=?,language=?,bio=? WHERE id=?", (display_name, handle, region, language, bio, g.user["id"]))
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    followed = query_all("SELECT m.* FROM follows f JOIN maps m ON m.id=f.map_id WHERE f.user_id=? ORDER BY f.created_at DESC", (g.user["id"],))
    my_rooms = query_all("SELECT r.*,m.name AS map_name,m.platform FROM rooms r JOIN maps m ON m.id=r.map_id WHERE r.host_id=? ORDER BY r.created_at DESC LIMIT 10", (g.user["id"],))
    friend_count = len(accepted_friend_ids(g.user["id"]))
    my_events = event_query("AND (e.host_id=? OR EXISTS (SELECT 1 FROM event_attendees ea WHERE ea.event_id=e.id AND ea.user_id=?)) AND e.starts_at>?", (g.user["id"], g.user["id"], iso(utcnow())))[:10]
    review_count = query_one("SELECT COUNT(*) AS c FROM map_reviews WHERE user_id=?", (g.user["id"],))["c"]
    return render_template("profile.html", followed=followed, my_rooms=my_rooms, friend_count=friend_count, my_events=my_events, review_count=review_count)


@app.route("/creator")
@creator_required
def creator_dashboard():
    owned_maps = query_all(
        """SELECT m.*,
            (SELECT COUNT(*) FROM rooms r WHERE r.map_id=m.id) AS total_rooms,
            (SELECT COUNT(*) FROM follows f WHERE f.map_id=m.id) AS followers
            FROM maps m WHERE m.creator_id=? ORDER BY m.active_players DESC""",
        (g.user["id"],),
    )
    if g.user["is_admin"]:
        owned_maps = query_all(
            """SELECT m.*,
            (SELECT COUNT(*) FROM rooms r WHERE r.map_id=m.id) AS total_rooms,
            (SELECT COUNT(*) FROM follows f WHERE f.map_id=m.id) AS followers
            FROM maps m ORDER BY m.active_players DESC"""
        )
    total_rooms = sum(m["total_rooms"] for m in owned_maps) if owned_maps else 0
    total_followers = sum(m["followers"] for m in owned_maps) if owned_maps else 0
    return render_template("creator_dashboard.html", owned_maps=owned_maps, total_rooms=total_rooms, total_followers=total_followers)


@app.route("/maps/add", methods=["GET", "POST"])
@login_required
def creator_new_map():
    selected_platform = request.form.get("platform", PLATFORMS[0])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        platform = request.form.get("platform", "")
        map_code, reference_error = validate_map_reference(platform, request.form.get("map_code", ""))
        description = request.form.get("description", "").strip()
        genre = request.form.get("genre", "").strip()
        max_party = request.form.get("max_party", type=int) or 4
        session_minutes = request.form.get("session_minutes", type=int) or 20
        difficulty = request.form.get("difficulty", "Intermediate")
        version = request.form.get("version", "Launch").strip() or "Launch"
        confirms_real_code = request.form.get("confirm_real_code") == "yes"

        error = None
        if len(name) < 3:
            error = "Enter the map's real published name."
        elif platform not in PLATFORMS:
            error = "Choose the game where this map is published."
        elif reference_error:
            error = reference_error
        elif not confirms_real_code:
            error = "Confirm that this is the exact working code or ID shown in the game."
        elif not description:
            error = "Add a short description so players know what the map is about."
        elif query_one("SELECT id FROM maps WHERE lower(platform)=lower(?) AND lower(map_code)=lower(?)", (platform, map_code)):
            error = "That game and map code are already listed in SquadFinder."

        if error:
            flash(error, "error")
        else:
            map_id = execute(
                """INSERT INTO maps (name,platform,map_code,description,genre,max_party,session_minutes,difficulty,active_players,verified,creator_id,badge,version,updated_at)
                VALUES (?,?,?,?,?,?,?,?,0,0,?,'Community',?,?)""",
                (name, platform, map_code, description[:1200], genre or "Custom", max(2, min(max_party, 100)), max(5, min(session_minutes, 240)), difficulty, g.user["id"], version[:80], iso(utcnow())),
            )
            if not g.user["is_creator"]:
                execute("UPDATE users SET is_creator=1 WHERE id=?", (g.user["id"],))
            log_activity(g.user["id"], "submitted a real game map", name, url_for("map_detail", map_id=map_id))
            flash("Real game map submitted. It is marked Community until platform verification is connected.", "success")
            return redirect(url_for("map_detail", map_id=map_id))
    return render_template("creator_map_form.html", selected_platform=selected_platform)


@app.get("/creator/maps/new")
def creator_new_map_legacy():
    return redirect(url_for("creator_new_map"), code=308)


@app.route("/community")
@login_required
def community():
    friends = query_all(
        """SELECT u.*,f.updated_at
           FROM friendships f
           JOIN users u ON u.id=CASE WHEN f.user_low_id=? THEN f.user_high_id ELSE f.user_low_id END
           WHERE f.status='accepted' AND (f.user_low_id=? OR f.user_high_id=?)
           ORDER BY u.display_name COLLATE NOCASE""",
        (g.user["id"], g.user["id"], g.user["id"]),
    )
    incoming = query_all(
        """SELECT u.*,f.created_at
           FROM friendships f JOIN users u ON u.id=f.requested_by_id
           WHERE f.status='pending' AND f.requested_by_id<>?
             AND (f.user_low_id=? OR f.user_high_id=?)
           ORDER BY f.created_at DESC""",
        (g.user["id"], g.user["id"], g.user["id"]),
    )
    outgoing = query_all(
        """SELECT u.*,f.created_at
           FROM friendships f
           JOIN users u ON u.id=CASE WHEN f.user_low_id=? THEN f.user_high_id ELSE f.user_low_id END
           WHERE f.status='pending' AND f.requested_by_id=?
           ORDER BY f.created_at DESC""",
        (g.user["id"], g.user["id"]),
    )
    suggestions = query_all(
        """SELECT u.* FROM users u
           WHERE u.id<>? AND NOT EXISTS (
             SELECT 1 FROM friendships f
             WHERE (f.user_low_id=MIN(u.id,?) AND f.user_high_id=MAX(u.id,?))
           )
           ORDER BY u.created_at DESC LIMIT 12""",
        (g.user["id"], g.user["id"], g.user["id"]),
    )
    feed_ids = [g.user["id"]] + accepted_friend_ids(g.user["id"])
    placeholders = ",".join("?" for _ in feed_ids)
    feed = query_all(
        f"""SELECT a.*,u.display_name,u.username
            FROM activity_items a JOIN users u ON u.id=a.user_id
            WHERE a.user_id IN ({placeholders})
            ORDER BY a.created_at DESC LIMIT 50""",
        tuple(feed_ids),
    )
    return render_template("community.html", friends=friends, incoming=incoming, outgoing=outgoing, suggestions=suggestions, feed=feed)


@app.route("/user/<int:user_id>")
@login_required
def public_profile(user_id: int):
    user = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user:
        abort(404)
    relation = None if user_id == g.user["id"] else friendship_between(g.user["id"], user_id)
    activities = query_all("SELECT * FROM activity_items WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,))
    maps = query_all("SELECT * FROM maps WHERE creator_id=? ORDER BY updated_at DESC LIMIT 12", (user_id,))
    stats = {
        "friends": len(accepted_friend_ids(user_id)),
        "rooms": query_one("SELECT COUNT(*) AS c FROM rooms WHERE host_id=?", (user_id,))["c"],
        "reviews": query_one("SELECT COUNT(*) AS c FROM map_reviews WHERE user_id=?", (user_id,))["c"],
    }
    return render_template("public_profile.html", profile_user=user, relation=relation, activities=activities, maps=maps, stats=stats)


@app.post("/friend/<int:user_id>/request")
@login_required
def send_friend_request(user_id: int):
    if user_id == g.user["id"] or not query_one("SELECT id FROM users WHERE id=?", (user_id,)):
        abort(404)
    existing = friendship_between(g.user["id"], user_id)
    if existing:
        flash("A friendship or request already exists.", "info")
    else:
        low_id, high_id = friend_pair(g.user["id"], user_id)
        now_value = iso(utcnow())
        execute(
            """INSERT INTO friendships
               (user_low_id,user_high_id,requested_by_id,status,created_at,updated_at)
               VALUES (?,?,?,'pending',?,?)""",
            (low_id, high_id, g.user["id"], now_value, now_value),
        )
        notify_user(user_id, g.user["id"], "friend", "New friend request", f"{g.user['display_name']} wants to connect.", url_for("community"))
        flash("Friend request sent.", "success")
    return redirect(safe_next("public_profile", user_id=user_id))


@app.post("/friend/<int:user_id>/accept")
@login_required
def accept_friend_request(user_id: int):
    relation = friendship_between(g.user["id"], user_id)
    if not relation or relation["status"] != "pending" or relation["requested_by_id"] == g.user["id"]:
        abort(403)
    low_id, high_id = friend_pair(g.user["id"], user_id)
    execute("UPDATE friendships SET status='accepted',updated_at=? WHERE user_low_id=? AND user_high_id=?", (iso(utcnow()), low_id, high_id))
    other = query_one("SELECT display_name FROM users WHERE id=?", (user_id,))
    notify_user(user_id, g.user["id"], "friend", "Friend request accepted", f"{g.user['display_name']} accepted your friend request.", url_for("public_profile", user_id=g.user["id"]))
    log_activity(g.user["id"], "became friends with", other["display_name"] if other else "a player", url_for("public_profile", user_id=user_id))
    flash("You are now friends.", "success")
    return redirect(safe_next("community"))


@app.post("/friend/<int:user_id>/decline")
@login_required
def decline_friend_request(user_id: int):
    relation = friendship_between(g.user["id"], user_id)
    if relation and relation["status"] == "pending":
        low_id, high_id = friend_pair(g.user["id"], user_id)
        execute("DELETE FROM friendships WHERE user_low_id=? AND user_high_id=?", (low_id, high_id))
        flash("Friend request removed.", "success")
    return redirect(safe_next("community"))


@app.post("/friend/<int:user_id>/remove")
@login_required
def remove_friend(user_id: int):
    relation = friendship_between(g.user["id"], user_id)
    if relation and relation["status"] == "accepted":
        low_id, high_id = friend_pair(g.user["id"], user_id)
        execute("DELETE FROM friendships WHERE user_low_id=? AND user_high_id=?", (low_id, high_id))
        flash("Friend removed.", "success")
    return redirect(safe_next("community"))


@app.route("/notifications")
@login_required
def notifications():
    rows = query_all(
        """SELECT n.*,u.display_name AS actor_name,u.username AS actor_username
           FROM notifications n LEFT JOIN users u ON u.id=n.actor_id
           WHERE n.user_id=? ORDER BY n.created_at DESC LIMIT 100""",
        (g.user["id"],),
    )
    return render_template("notifications.html", notifications=rows)


@app.get("/notification/<int:notification_id>/open")
@login_required
def open_notification(notification_id: int):
    row = query_one("SELECT * FROM notifications WHERE id=? AND user_id=?", (notification_id, g.user["id"]))
    if not row:
        abort(404)
    execute("UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,))
    target = row["link"]
    return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("notifications"))


@app.post("/notifications/read-all")
@login_required
def read_all_notifications():
    execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (g.user["id"],))
    flash("Notifications marked as read.", "success")
    return redirect(url_for("notifications"))


@app.post("/map/<int:map_id>/review")
@login_required
def review_map(map_id: int):
    map_row = query_one("SELECT id,name,creator_id FROM maps WHERE id=?", (map_id,))
    if not map_row:
        abort(404)
    rating = request.form.get("rating", type=int) or 0
    body = " ".join(request.form.get("body", "").strip().split())[:600]
    if rating not in range(1, 6):
        flash("Choose a rating from 1 to 5 stars.", "error")
    elif body and len(body) < 8:
        flash("Write at least 8 characters or leave the review text empty.", "error")
    else:
        now_value = iso(utcnow())
        execute(
            """INSERT INTO map_reviews (map_id,user_id,rating,body,created_at,updated_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(map_id,user_id) DO UPDATE SET
                 rating=excluded.rating,body=excluded.body,updated_at=excluded.updated_at""",
            (map_id, g.user["id"], rating, body, now_value, now_value),
        )
        log_activity(g.user["id"], f"rated a map {rating}/5", map_row["name"], url_for("map_detail", map_id=map_id))
        if map_row["creator_id"]:
            notify_user(map_row["creator_id"], g.user["id"], "review", "New rating on your map", f"{g.user['display_name']} rated {map_row['name']} {rating}/5.", url_for("map_detail", map_id=map_id))
        flash("Your map rating was saved.", "success")
    return redirect(url_for("map_detail", map_id=map_id) + "#map-reviews")


@app.route("/events")
def events_list():
    platform = request.args.get("platform", "").strip()
    where = "AND e.starts_at>?"
    params: list[Any] = [iso(utcnow())]
    if platform:
        where += " AND m.platform=?"
        params.append(platform)
    events = event_query(where, tuple(params))
    return render_template("events.html", events=events, selected_platform=platform)


@app.route("/events/new", methods=["GET", "POST"])
@login_required
def create_event():
    maps = query_all("SELECT id,name,platform,map_code FROM maps ORDER BY active_players DESC,name")
    preselected = request.args.get("map_id", type=int)
    if request.method == "POST":
        map_id = request.form.get("map_id", type=int)
        title = request.form.get("title", "").strip()
        starts_at = parse_local_event_datetime(request.form.get("starts_at", ""))
        duration = request.form.get("duration_minutes", type=int) or 60
        max_players = request.form.get("max_players", type=int) or 8
        region = request.form.get("region", "Auto")
        language = request.form.get("language", "English")
        mic = request.form.get("mic", "Optional")
        note = request.form.get("note", "").strip()[:800]
        map_row = query_one("SELECT id,name FROM maps WHERE id=?", (map_id,)) if map_id else None
        error = None
        if not map_row:
            error = "Choose a valid map."
        elif len(title) < 4:
            error = "Add a clear event title."
        elif not starts_at or starts_at <= utcnow() + timedelta(minutes=5):
            error = "Choose a start time at least 5 minutes in the future."
        elif duration < 15 or duration > 480:
            error = "Event duration must be between 15 minutes and 8 hours."
        elif max_players < 2 or max_players > 100:
            error = "Event size must be between 2 and 100 players."
        if error:
            flash(error, "error")
        else:
            event_id = execute(
                """INSERT INTO gaming_events
                   (map_id,host_id,title,starts_at,duration_minutes,max_players,region,language,mic,note,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'scheduled',?)""",
                (map_id, g.user["id"], title, iso(starts_at), duration, max_players, region, language, mic, note, iso(utcnow())),
            )
            execute("INSERT INTO event_attendees (event_id,user_id,joined_at) VALUES (?,?,?)", (event_id, g.user["id"], iso(utcnow())))
            log_activity(g.user["id"], "scheduled a gaming event", map_row["name"], url_for("event_detail", event_id=event_id))
            flash("Gaming event scheduled.", "success")
            return redirect(url_for("event_detail", event_id=event_id))
    return render_template("create_event.html", maps=maps, preselected=preselected)


@app.route("/event/<int:event_id>")
def event_detail(event_id: int):
    rows = event_query("AND e.id=?", (event_id,))
    if not rows:
        event = query_one(
            """SELECT e.*,m.name AS map_name,m.platform,m.map_code,u.display_name AS host_name,u.username AS host_username,
                      (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id=e.id) AS attendee_count
               FROM gaming_events e JOIN maps m ON m.id=e.map_id JOIN users u ON u.id=e.host_id WHERE e.id=?""",
            (event_id,),
        )
    else:
        event = rows[0]
    if not event:
        abort(404)
    attendees = query_all(
        """SELECT u.*,ea.joined_at FROM event_attendees ea JOIN users u ON u.id=ea.user_id
           WHERE ea.event_id=? ORDER BY ea.joined_at""",
        (event_id,),
    )
    joined = bool(g.user and query_one("SELECT 1 FROM event_attendees WHERE event_id=? AND user_id=?", (event_id, g.user["id"])))
    return render_template("event_detail.html", event=event, attendees=attendees, joined=joined)


@app.post("/event/<int:event_id>/join")
@login_required
def join_event(event_id: int):
    event = query_one("SELECT * FROM gaming_events WHERE id=?", (event_id,))
    if not event or event["status"] != "scheduled" or (parse_dt(event["starts_at"]) or utcnow()) <= utcnow():
        flash("This event is no longer open for joining.", "error")
    elif query_one("SELECT 1 FROM event_attendees WHERE event_id=? AND user_id=?", (event_id, g.user["id"])):
        flash("You already joined this event.", "info")
    else:
        count = query_one("SELECT COUNT(*) AS c FROM event_attendees WHERE event_id=?", (event_id,))["c"]
        if count >= event["max_players"]:
            flash("This event is full.", "error")
        else:
            execute("INSERT INTO event_attendees (event_id,user_id,joined_at) VALUES (?,?,?)", (event_id, g.user["id"], iso(utcnow())))
            notify_user(event["host_id"], g.user["id"], "event", "A player joined your event", f"{g.user['display_name']} joined {event['title']}.", url_for("event_detail", event_id=event_id))
            log_activity(g.user["id"], "joined a gaming event", event["title"], url_for("event_detail", event_id=event_id))
            flash("You joined the event.", "success")
    return redirect(url_for("event_detail", event_id=event_id))


@app.post("/event/<int:event_id>/leave")
@login_required
def leave_event(event_id: int):
    event = query_one("SELECT * FROM gaming_events WHERE id=?", (event_id,))
    if not event:
        abort(404)
    if event["host_id"] == g.user["id"]:
        flash("Hosts can cancel the event instead of leaving.", "info")
    else:
        execute("DELETE FROM event_attendees WHERE event_id=? AND user_id=?", (event_id, g.user["id"]))
        flash("You left the event.", "success")
    return redirect(url_for("event_detail", event_id=event_id))


@app.post("/event/<int:event_id>/cancel")
@login_required
def cancel_event(event_id: int):
    event = query_one("SELECT * FROM gaming_events WHERE id=?", (event_id,))
    if not event:
        abort(404)
    if event["host_id"] != g.user["id"] and not g.user["is_admin"]:
        abort(403)
    execute("UPDATE gaming_events SET status='cancelled' WHERE id=?", (event_id,))
    attendees = query_all("SELECT user_id FROM event_attendees WHERE event_id=? AND user_id<>?", (event_id, g.user["id"]))
    for attendee in attendees:
        notify_user(attendee["user_id"], g.user["id"], "event", "Gaming event cancelled", event["title"], url_for("events_list"))
    flash("Event cancelled.", "success")
    return redirect(url_for("events_list"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE lower(email)=? OR lower(username)=?", (identity, identity))
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email/username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(24)
            session.permanent = True
            flash(f"Welcome back, {user['display_name']}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url if next_url and next_url.startswith("/") else url_for("home"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or not username.replace("_", "").isalnum():
            flash("Username must be at least 3 letters/numbers and may include underscores.", "error")
        elif "@" not in email:
            flash("Enter a valid email address.", "error")
        elif len(display_name) < 2:
            flash("Enter a display name.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif query_one("SELECT 1 FROM users WHERE lower(username)=? OR lower(email)=?", (username, email)):
            flash("That username or email is already registered.", "error")
        else:
            user_id = execute(
                """INSERT INTO users (username,email,password_hash,display_name,platform_handle,region,language,bio,is_creator,is_admin,created_at)
                VALUES (?,?,?,?,?,'Auto','English','',0,0,?)""",
                (username, email, generate_password_hash(password), display_name, display_name, iso(utcnow())),
            )
            session.clear()
            session["user_id"] = user_id
            session["csrf_token"] = secrets.token_urlsafe(24)
            session.permanent = True
            flash("Account created. Complete your profile and start matching.", "success")
            return redirect(url_for("profile"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("home"))



@app.get("/api/room/<int:room_id>/messages")
def room_messages(room_id: int):
    _, error = get_api_room_member(room_id)
    if error:
        return error
    after = max(0, request.args.get("after", 0, type=int) or 0)
    if after:
        rows = query_all(
            """SELECT rm.id,rm.body,rm.created_at,u.id AS user_id,u.display_name,u.username
               FROM room_messages rm JOIN users u ON u.id=rm.user_id
               WHERE rm.room_id=? AND rm.id>? ORDER BY rm.id ASC LIMIT 100""",
            (room_id, after),
        )
    else:
        rows = query_all(
            """SELECT * FROM (
                   SELECT rm.id,rm.body,rm.created_at,u.id AS user_id,u.display_name,u.username
                   FROM room_messages rm JOIN users u ON u.id=rm.user_id
                   WHERE rm.room_id=? ORDER BY rm.id DESC LIMIT 75
               ) ORDER BY id ASC""",
            (room_id,),
        )
    return jsonify({
        "ok": True,
        "messages": [
            {
                "id": row["id"],
                "body": row["body"],
                "created_at": row["created_at"],
                "user_id": row["user_id"],
                "display_name": row["display_name"],
                "username": row["username"],
            }
            for row in rows
        ],
    })


@app.post("/api/room/<int:room_id>/messages")
def send_room_message(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    data = request.get_json(silent=True) or request.form
    raw_body = str(data.get("body", "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    body = "\n".join(" ".join(line.split()) for line in raw_body.split("\n")).strip()
    if not body:
        return api_error("Write a message first.", 400)
    if len(body) > 1000:
        return api_error("Messages are limited to 1,000 characters.", 400)
    latest = query_one(
        "SELECT created_at FROM room_messages WHERE room_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
        (room_id, g.user["id"]),
    )
    if latest and parse_dt(latest["created_at"]):
        if (utcnow() - parse_dt(latest["created_at"])).total_seconds() < 0.7:
            return api_error("Please wait a moment before sending another message.", 429)
    message_id = execute(
        "INSERT INTO room_messages (room_id,user_id,body,created_at) VALUES (?,?,?,?)",
        (room_id, g.user["id"], body, iso(utcnow())),
    )
    return jsonify({"ok": True, "message_id": message_id}), 201


@app.post("/api/room/<int:room_id>/voice/join")
def voice_join(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not valid_voice_session(session_id):
        return api_error("Invalid voice session.", 400)
    previous_sessions = query_all(
        "SELECT session_id FROM voice_presence WHERE room_id=? AND user_id=?",
        (room_id, g.user["id"]),
    )
    execute("DELETE FROM voice_presence WHERE room_id=? AND user_id=?", (room_id, g.user["id"]))
    for previous in previous_sessions:
        execute(
            "DELETE FROM voice_signals WHERE room_id=? AND (sender_session=? OR target_session=?)",
            (room_id, previous["session_id"], previous["session_id"]),
        )
    cutoff = iso(utcnow() - timedelta(seconds=45))
    peers = query_all(
        """SELECT vp.session_id,vp.muted,vp.deafened,u.id AS user_id,u.display_name,u.username
           FROM voice_presence vp JOIN users u ON u.id=vp.user_id
           WHERE vp.room_id=? AND vp.last_seen>? AND vp.session_id<>?
           ORDER BY vp.joined_at""",
        (room_id, cutoff, session_id),
    )
    if len(peers) >= VOICE_MAX_PARTICIPANTS:
        return api_error(f"This browser voice channel is limited to {VOICE_MAX_PARTICIPANTS} participants.", 409)
    now_value = iso(utcnow())
    execute(
        """INSERT INTO voice_presence
           (room_id,user_id,session_id,muted,deafened,joined_at,last_seen)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(room_id,user_id,session_id) DO UPDATE SET last_seen=excluded.last_seen""",
        (room_id, g.user["id"], session_id, 0, 0, now_value, now_value),
    )
    return jsonify({"ok": True, "peers": [dict(peer) for peer in peers]})


@app.post("/api/room/<int:room_id>/voice/heartbeat")
def voice_heartbeat(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not valid_voice_session(session_id):
        return api_error("Invalid voice session.", 400)
    muted = 1 if data.get("muted") else 0
    deafened = 1 if data.get("deafened") else 0
    execute(
        """UPDATE voice_presence SET last_seen=?,muted=?,deafened=?
           WHERE room_id=? AND user_id=? AND session_id=?""",
        (iso(utcnow()), muted, deafened, room_id, g.user["id"], session_id),
    )
    return jsonify({"ok": True})


@app.get("/api/room/<int:room_id>/voice/peers")
def voice_peers(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    session_id = request.args.get("session_id", "")
    if not valid_voice_session(session_id):
        return api_error("Invalid voice session.", 400)
    peers = query_all(
        """SELECT vp.session_id,vp.muted,vp.deafened,u.id AS user_id,u.display_name,u.username
           FROM voice_presence vp JOIN users u ON u.id=vp.user_id
           WHERE vp.room_id=? AND vp.last_seen>? AND vp.session_id<>?
           ORDER BY vp.joined_at""",
        (room_id, iso(utcnow() - timedelta(seconds=45)), session_id),
    )
    return jsonify({"ok": True, "peers": [dict(peer) for peer in peers]})


@app.post("/api/room/<int:room_id>/voice/signal")
def voice_signal(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    sender = data.get("session_id")
    target = data.get("target_session")
    payload = data.get("payload")
    if not valid_voice_session(sender) or not valid_voice_session(target) or sender == target:
        return api_error("Invalid voice signaling session.", 400)
    if not isinstance(payload, dict) or payload.get("type") not in {"offer", "answer", "ice"}:
        return api_error("Invalid voice signal.", 400)
    encoded = json.dumps(payload, separators=(",", ":"))
    if len(encoded) > 30000:
        return api_error("Voice signal is too large.", 400)
    sender_row = query_one(
        "SELECT 1 FROM voice_presence WHERE room_id=? AND user_id=? AND session_id=?",
        (room_id, g.user["id"], sender),
    )
    target_row = query_one(
        "SELECT 1 FROM voice_presence WHERE room_id=? AND session_id=? AND last_seen>?",
        (room_id, target, iso(utcnow() - timedelta(seconds=45))),
    )
    if not sender_row or not target_row:
        return api_error("A voice participant disconnected.", 409)
    execute(
        """INSERT INTO voice_signals
           (room_id,sender_session,target_session,payload,created_at)
           VALUES (?,?,?,?,?)""",
        (room_id, sender, target, encoded, iso(utcnow())),
    )
    return jsonify({"ok": True})


def consume_voice_signals(room_id: int, session_id: str) -> list[Any]:
    """Read and delete queued WebRTC signals in one transaction."""
    select_sql = """SELECT id,sender_session,payload FROM voice_signals
                    WHERE room_id=? AND target_session=? ORDER BY id LIMIT 100"""
    if USE_POSTGRES:
        pool = get_postgres_pool()
        with pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(postgres_sql(select_sql) + " FOR UPDATE", (room_id, session_id))
                    rows = cur.fetchall()
                    if rows:
                        placeholders = ",".join("%s" for _ in rows)
                        cur.execute(
                            f"DELETE FROM voice_signals WHERE id IN ({placeholders})",
                            tuple(row["id"] for row in rows),
                        )
                conn.commit()
                return rows
            except Exception:
                conn.rollback()
                raise

    conn = sqlite3.connect(app.config["DATABASE"], timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=8000")
    try:
        rows = conn.execute(select_sql, (room_id, session_id)).fetchall()
        if rows:
            placeholders = ",".join("?" for _ in rows)
            conn.execute(
                f"DELETE FROM voice_signals WHERE id IN ({placeholders})",
                tuple(row["id"] for row in rows),
            )
        conn.commit()
        return rows
    finally:
        conn.close()


@app.get("/api/room/<int:room_id>/voice/signals")
def voice_signals(room_id: int):
    _, error = get_api_room_member(room_id, require_open=True)
    if error:
        return error
    session_id = request.args.get("session_id", "")
    if not valid_voice_session(session_id):
        return api_error("Invalid voice session.", 400)
    own_presence = query_one(
        "SELECT 1 FROM voice_presence WHERE room_id=? AND user_id=? AND session_id=?",
        (room_id, g.user["id"], session_id),
    )
    if not own_presence:
        return api_error("Voice session is no longer active.", 409)
    rows = consume_voice_signals(room_id, session_id)
    signals = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        signals.append({"sender_session": row["sender_session"], "payload": payload})
    return jsonify({"ok": True, "signals": signals})


@app.post("/api/room/<int:room_id>/voice/leave")
def voice_leave(room_id: int):
    _, error = get_api_room_member(room_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not valid_voice_session(session_id):
        return api_error("Invalid voice session.", 400)
    execute(
        "DELETE FROM voice_presence WHERE room_id=? AND user_id=? AND session_id=?",
        (room_id, g.user["id"], session_id),
    )
    execute(
        "DELETE FROM voice_signals WHERE room_id=? AND (sender_session=? OR target_session=?)",
        (room_id, session_id, session_id),
    )
    return jsonify({"ok": True})


@app.get("/healthz")
def healthz():
    try:
        query_one("SELECT 1 AS ok")
        return jsonify({"ok": True, "database": "supabase-postgres" if USE_POSTGRES else "sqlite"})
    except Exception as exc:
        app.logger.exception("Health check failed")
        return jsonify({"ok": False, "error": type(exc).__name__}), 503


@app.route("/api/rooms")
def api_rooms():
    rooms = get_active_rooms()
    return jsonify({
        "updated_at": iso(utcnow()),
        "rooms": [
            {
                "id": r["id"],
                "title": r["title"],
                "map_name": r["map_name"],
                "platform": r["platform"],
                "current_members": r["current_members"],
                "party_size": r["party_size"],
                "spots_left": r["spots_left"],
                "expires_at": r["expires_at"],
            }
            for r in rooms
        ],
    })


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message="The request could not be completed. Refresh the page and try again."), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template("error.html", code=403, message="You do not have permission to open this page."), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="That page, map, or squad room could not be found."), 404


if __name__ == "__main__":
    ssl_context = None
    if USE_HTTPS:
        cert_path = os.environ.get(
            "SQUADFINDER_SSL_CERT",
            str(TRUSTED_HTTPS_DIR / "squadfinder_server.crt"),
        )
        key_path = os.environ.get(
            "SQUADFINDER_SSL_KEY",
            str(TRUSTED_HTTPS_DIR / "squadfinder_server_key.pem"),
        )
        if not Path(cert_path).exists() or not Path(key_path).exists():
            raise RuntimeError(
                "Trusted HTTPS files are missing. Run START_WINDOWS.bat so SquadFinder can create them."
            )
        ssl_context = (cert_path, key_path)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5443" if USE_HTTPS else "5000")),
        debug=False,
        ssl_context=ssl_context,
        threaded=True,
    )
