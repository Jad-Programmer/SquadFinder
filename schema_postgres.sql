CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
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
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (LOWER(username));
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS maps (
    id BIGSERIAL PRIMARY KEY,
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
    creator_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    badge TEXT NOT NULL DEFAULT 'New',
    version TEXT NOT NULL DEFAULT 'Launch',
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_maps_platform_code_lower ON maps (LOWER(platform), LOWER(map_code));

CREATE TABLE IF NOT EXISTS rooms (
    id BIGSERIAL PRIMARY KEY,
    map_id BIGINT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    host_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id BIGINT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (room_id,user_id)
);

CREATE TABLE IF NOT EXISTS guides (
    id BIGSERIAL PRIMARY KEY,
    map_id BIGINT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    guide_type TEXT NOT NULL DEFAULT 'Strategy',
    helpful_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guide_votes (
    guide_id BIGINT NOT NULL REFERENCES guides(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (guide_id,user_id)
);

CREATE TABLE IF NOT EXISTS follows (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    map_id BIGINT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id,map_id)
);

CREATE TABLE IF NOT EXISTS room_messages (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_presence (
    room_id BIGINT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    muted INTEGER NOT NULL DEFAULT 0,
    deafened INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (room_id, user_id, session_id)
);

CREATE TABLE IF NOT EXISTS voice_signals (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    sender_session TEXT NOT NULL,
    target_session TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS friendships (
    user_low_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    requested_by_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_low_id, user_high_id),
    CHECK (user_low_id < user_high_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    kind TEXT NOT NULL DEFAULT 'general',
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verb TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS map_reviews (
    map_id BIGINT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (map_id, user_id)
);

CREATE TABLE IF NOT EXISTS gaming_events (
    id BIGSERIAL PRIMARY KEY,
    map_id BIGINT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    host_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    max_players INTEGER NOT NULL DEFAULT 8,
    region TEXT NOT NULL DEFAULT 'Auto',
    language TEXT NOT NULL DEFAULT 'English',
    mic TEXT NOT NULL DEFAULT 'Optional',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_attendees (
    event_id BIGINT NOT NULL REFERENCES gaming_events(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_rooms_active ON rooms(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_rooms_map ON rooms(map_id);
CREATE INDEX IF NOT EXISTS idx_maps_platform ON maps(platform);
CREATE INDEX IF NOT EXISTS idx_room_messages_room ON room_messages(room_id, id);
CREATE INDEX IF NOT EXISTS idx_voice_presence_room ON voice_presence(room_id, last_seen);
CREATE INDEX IF NOT EXISTS idx_voice_signals_target ON voice_signals(room_id, target_session, id);
CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_items(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_map ON map_reviews(map_id, rating);
CREATE INDEX IF NOT EXISTS idx_events_start ON gaming_events(status, starts_at);
CREATE INDEX IF NOT EXISTS idx_event_attendees_event ON event_attendees(event_id);
