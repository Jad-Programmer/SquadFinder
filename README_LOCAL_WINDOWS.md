# MetaVerse SquadFinder — Discord Theme + Trusted HTTPS Edition

A Flask MVP for squad formation around user-generated maps and custom-game communities.


## Squad chat and voice update

- Persistent private text chat inside every squad room
- Chat access restricted to users who joined that room
- Live message polling without page refreshes
- Browser WebRTC voice rooms with peer-to-peer audio (up to 8 participants)
- Join/disconnect, mute, deafen, participant presence, and connection states
- Voice signaling is carried through the Flask/SQLite server; audio is not stored or recorded
- Stale voice sessions and signaling records are removed automatically
- `START_WINDOWS.bat` now starts the full app, chat, and voice through trusted local HTTPS
- `START_WINDOWS_VOICE_HTTPS.bat` points to the same trusted launcher for backward compatibility

For voice across different internet networks, deploy SquadFinder behind trusted HTTPS and configure a TURN relay. Public STUN is included, but STUN alone cannot traverse every firewall or NAT configuration.

Optional TURN relay configuration for production:

```text
SQUADFINDER_TURN_URL=turn:turn.example.com:3478
SQUADFINDER_TURN_USERNAME=your-username
SQUADFINDER_TURN_CREDENTIAL=your-password
```

## Discord-inspired interface update

- New desktop app shell with a narrow server/game rail
- Channel-style navigation sidebar for Discover, Live Squads, Quick Match, and Creator tools
- Discord-inspired charcoal workspace and blurple accent controls
- Compact signed-in user panel with profile and logout shortcuts
- Flat cards, filters, forms, tabs, tables, room panels, and creator screens
- Slide-out mobile channel sidebar with a backdrop and close control
- All previous games, maps, routes, accounts, SQLite data, and functional behavior preserved
- This is an original interface inspired by the general layout style; no Discord logo or proprietary assets are included

## Expanded catalog included

- **12 supported games**
- **48 built-in demonstration maps** — four maps per game
- **12 demonstration LFG rooms** across different games on a fresh install
- Homepage now displays up to 12 trending maps instead of 6
- New **Browse by game** section with map and activity counts
- New game tiles and visual identities for every supported game
- Discover page now has game-count shortcuts and a denser responsive map grid
- Search now also matches game/platform names
- New sorting: most active, most live rooms, recently updated, and name A–Z
- Additive catalog migration for existing databases

## Supported games

- Fortnite Creative
- Roblox
- Minecraft
- GTA V FiveM
- Halo Infinite Forge
- Fall Guys Creative
- Rec Room
- VRChat
- Core Games
- Garry's Mod
- Counter-Strike 2 Workshop
- Trackmania

## Existing features

- Individual map pages with codes, metadata, followers, active rooms, and strategy guides
- Temporary LFG rooms that expire automatically
- Join, leave, and close-room flows
- Quick Match based on game, play style, region, and language
- Player profiles and platform handles
- Followed-map watchlist
- Creator console and new-map publishing
- Helpful voting for guides
- Mobile-responsive Discord-inspired dark interface
- SQLite persistence, password hashing, CSRF protection, security headers, and safe session defaults
- JSON room endpoint with lightweight live polling
- Private squad text chat and browser WebRTC voice channels

## Windows installation

1. Extract the ZIP.
2. Double-click `START_WINDOWS.bat`.
3. The script creates a virtual environment, installs the requirements, opens the browser, and starts the app.
4. Open `https://localhost:5443` if the browser does not open automatically.
5. The launcher creates a private local CA and trusts its public certificate for the current Windows user before opening the browser, so Chrome/Edge should show a normal secure connection instead of a red self-signed warning.

Python 3.10 or newer is recommended.


## Trusted local HTTPS

The default Windows launcher no longer uses Werkzeug's temporary self-signed certificate. On first start it creates a private certificate authority in `%LOCALAPPDATA%\MetaVerseSquadFinder\trusted_https`, trusts only the public certificate for the current Windows user, and generates a server certificate for `localhost`, `127.0.0.1`, the computer name, and current LAN addresses. The CA private key never leaves that local folder.

The secure launcher also enables Secure/HttpOnly cookies, a Content Security Policy, and cross-origin security headers. Use exactly `https://localhost:5443` on the same computer. If the browser was already running during the first trust installation, close all browser windows once and start SquadFinder again.

For a phone or second computer, that separate device must trust the public `.cer` file, or the app must be deployed behind a real domain with a publicly trusted certificate. Run `REMOVE_SQUADFINDER_LOCAL_CERTIFICATE.bat` to remove the local CA from the Windows user trust store.

## Upgrading from the previous SquadFinder version

1. Close the old app.
2. Copy the old folder's `instance` directory into this new `metaverse_squadfinder` folder.
3. Keep the file `instance/squadfinder.db` intact.
4. Start the new version with `START_WINDOWS.bat`.
5. On startup, SquadFinder adds only missing built-in games and maps. It does not replace user accounts, rooms, followed maps, guides, or creator-published maps.

The SQLite database is stored at:

```text
instance/squadfinder.db
```

Back up that file before any upgrade.

## Demo logins

- Player: `demo` / `demo123`
- Creator: `creator` / `creator123`
- Administrator: `admin` / `admin123`

Change or remove these accounts before public deployment.

## Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

## Production deployment

Set a persistent secret key before deployment:

```bash
export SQUADFINDER_SECRET_KEY="replace-with-a-long-random-value"
```

Then run with a production WSGI server:

```bash
gunicorn -w 3 -b 0.0.0.0:8000 app:app
```

## Important data note

All built-in map names, codes, player counts, versions, and activity signals are fictional demonstration data. Live statistics and real map imports require separate official or creator-authorized integrations for each game platform.

## Adding real game maps

Every signed-in user now sees **Add real game map** in the Discord-style sidebar and map discovery page. The user must select the game and paste the exact working map code, experience ID, public URL, world ID, Realm/server address, or Workshop ID shown by that game. Placeholder/demo references and duplicate game+code combinations are rejected. New user submissions receive a **Community** badge and are not automatically marked verified. After a user's first successful submission, their account gains creator-console access.

SquadFinder currently validates format and user confirmation; it does not contact every game platform to prove that the code exists. Platform API verification can be integrated separately.

## Simplified navigation update

The separate circular server/game rail has been removed. Every destination remains available from the normal left sidebar, the desktop top-bar shortcuts, and the mobile bottom navigation. The sidebar search now searches the map catalog by name or real game code.


## Community Feature Pack 1.1

This version adds friend requests, public player profiles, a friends activity feed, notifications, map ratings and written reviews, and scheduled gaming events. The database update is additive: existing accounts, maps, squad rooms, chats, voice data, follows, and guides remain in place.
