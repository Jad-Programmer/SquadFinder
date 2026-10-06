PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    platform_handle TEXT,
    region TEXT NOT NULL DEFAULT 'Auto',
    language TEXT NOT NULL DEFAULT 'English',
    bio TEXT NOT NULL DEFAULT '',
    is_creator INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    map_code TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT 'Custom',
    max_party INTEGER NOT NULL DEFAULT 4,
    session_minutes INTEGER NOT NULL DEFAULT 20,
    difficulty TEXT NOT NULL DEFAULT 'Intermediate',
    active_players INTEGER NOT NULL DEFAULT 0,
    verified INTEGER NOT NULL DEFAULT 0,
    creator_id INTEGER,
    badge TEXT NOT NULL DEFAULT 'New',
    version TEXT NOT NULL DEFAULT 'Launch',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    play_style TEXT NOT NULL,
    region TEXT NOT NULL,
    language TEXT NOT NULL,
    mic TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    current_members INTEGER NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (room_id,user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    guide_type TEXT NOT NULL DEFAULT 'Strategy',
    helpful_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS guide_votes (
    guide_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (guide_id,user_id),
    FOREIGN KEY (guide_id) REFERENCES guides(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS follows (
    user_id INTEGER NOT NULL,
    map_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id,map_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rooms_active ON rooms(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_rooms_map ON rooms(map_id);
CREATE INDEX IF NOT EXISTS idx_maps_platform ON maps(platform);


CREATE TABLE IF NOT EXISTS room_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voice_presence (
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    muted INTEGER NOT NULL DEFAULT 0,
    deafened INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (room_id, user_id, session_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voice_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    sender_session TEXT NOT NULL,
    target_session TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_messages_room ON room_messages(room_id, id);
CREATE INDEX IF NOT EXISTS idx_voice_presence_room ON voice_presence(room_id, last_seen);
CREATE INDEX IF NOT EXISTS idx_voice_signals_target ON voice_signals(room_id, target_session, id);

-- Community feature pack: friends, notifications, reviews, events, and activity
CREATE TABLE IF NOT EXISTS friendships (
    user_low_id INTEGER NOT NULL,
    user_high_id INTEGER NOT NULL,
    requested_by_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_low_id, user_high_id),
    CHECK (user_low_id < user_high_id),
    FOREIGN KEY (user_low_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_high_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (requested_by_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    actor_id INTEGER,
    kind TEXT NOT NULL DEFAULT 'general',
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS activity_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    verb TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS map_reviews (
    map_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (map_id, user_id),
    CHECK (rating BETWEEN 1 AND 5),
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gaming_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    max_players INTEGER NOT NULL DEFAULT 8,
    region TEXT NOT NULL DEFAULT 'Auto',
    language TEXT NOT NULL DEFAULT 'English',
    mic TEXT NOT NULL DEFAULT 'Optional',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TEXT NOT NULL,
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_attendees (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (event_id, user_id),
    FOREIGN KEY (event_id) REFERENCES gaming_events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_items(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_map ON map_reviews(map_id, rating);
CREATE INDEX IF NOT EXISTS idx_events_start ON gaming_events(status, starts_at);
CREATE INDEX IF NOT EXISTS idx_event_attendees_event ON event_attendees(event_id);
