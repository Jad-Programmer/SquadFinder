"""Built-in demonstration catalog for MetaVerse SquadFinder.

All names, codes, counts, and activity values are fictional placeholders. They are
kept in one file so the catalog can grow without making the Flask routes harder
to maintain.
"""

PLATFORMS = [
    "Fortnite Creative",
    "Roblox",
    "Minecraft",
    "GTA V FiveM",
    "Halo Infinite Forge",
    "Fall Guys Creative",
    "Rec Room",
    "VRChat",
    "Core Games",
    "Garry's Mod",
    "Counter-Strike 2 Workshop",
    "Trackmania",
]

PLATFORM_SHORT = {
    "Fortnite Creative": "FN",
    "Roblox": "RB",
    "Minecraft": "MC",
    "GTA V FiveM": "5M",
    "Halo Infinite Forge": "HI",
    "Fall Guys Creative": "FG",
    "Rec Room": "RR",
    "VRChat": "VR",
    "Core Games": "CG",
    "Garry's Mod": "GM",
    "Counter-Strike 2 Workshop": "CS",
    "Trackmania": "TM",
}

# owner is either "creator" or "admin" and resolves to the corresponding
# seeded account at install time.
DEMO_MAPS = [
    # Fortnite Creative
    dict(name="Neon Heist: Co-op Escape", platform="Fortnite Creative", code="4821-7390-1158", description="Stealth through a neon vault, coordinate switches, and escape before lockdown.", genre="Stealth", party=4, minutes=18, difficulty="Intermediate", active=742, verified=1, owner="creator", badge="Featured", version="v2.4", hours=6),
    dict(name="Zero Build Red vs Blue Lab", platform="Fortnite Creative", code="9130-2244-6712", description="Fast team fights with rotating experimental loadouts and ranked rounds.", genre="PvP", party=12, minutes=15, difficulty="Competitive", active=2116, verified=1, owner="creator", badge="Hot", version="v5.1", hours=3),
    dict(name="Pulse Parkour Duos", platform="Fortnite Creative", code="3029-8471-5560", description="Two-player synchronized parkour with shared checkpoints and time trials.", genre="Parkour", party=2, minutes=12, difficulty="Intermediate", active=683, verified=0, owner="creator", badge="Rising", version="v1.7", hours=18),
    dict(name="Stormline Extraction", platform="Fortnite Creative", code="7742-6118-3905", description="Loot a collapsing city, revive teammates, and reach extraction before the storm closes.", genre="Extraction", party=4, minutes=24, difficulty="Advanced", active=1448, verified=1, owner="creator", badge="Trending", version="v3.0", hours=5),

    # Roblox
    dict(name="Skyline Tycoon Rush", platform="Roblox", code="18402957321", description="Build fast, defend your rooftop business, and raid rival towers in short sessions.", genre="Tycoon", party=6, minutes=25, difficulty="Beginner", active=1280, verified=0, owner="creator", badge="Trending", version="Season 3", hours=12),
    dict(name="Midnight Mall Survival", platform="Roblox", code="18732209114", description="Survive waves, repair stores, and unlock hidden routes before sunrise.", genre="Survival", party=5, minutes=30, difficulty="Intermediate", active=918, verified=0, owner="creator", badge="Trending", version="Update 8", hours=9),
    dict(name="Cafe Chaos Roleplay", platform="Roblox", code="19002746073", description="Run a chaotic café, assign roles, serve customers, and handle surprise events.", genre="Roleplay", party=8, minutes=35, difficulty="Beginner", active=1603, verified=0, owner="creator", badge="Popular", version="Summer", hours=22),
    dict(name="Abyss Research Facility", platform="Roblox", code="19284017456", description="Restore power, decode specimens, and escape a cooperative underwater horror facility.", genre="Horror", party=6, minutes=40, difficulty="Advanced", active=1107, verified=1, owner="creator", badge="Featured", version="Chapter 2", hours=7),

    # Minecraft
    dict(name="Block Harbor: Island Trials", platform="Minecraft", code="play.blockharbor.test", description="A rotating set of survival trials, puzzle rooms, and cooperative boss fights.", genre="Adventure", party=8, minutes=45, difficulty="Intermediate", active=364, verified=0, owner="admin", badge="Rising", version="1.21 Demo", hours=24),
    dict(name="Copperstone SMP Events", platform="Minecraft", code="copperstone.test:25565", description="Weekly community events, team quests, treasure hunts, and build competitions.", genre="SMP", party=10, minutes=60, difficulty="Casual", active=155, verified=0, owner="admin", badge="Community", version="August", hours=48),
    dict(name="Redstone Relay Championship", platform="Minecraft", code="relaycraft.test", description="Teams build timed redstone solutions across increasingly difficult engineering rounds.", genre="Puzzle", party=6, minutes=40, difficulty="Advanced", active=286, verified=1, owner="admin", badge="Challenge", version="Circuit 4", hours=14),
    dict(name="Frostkeep Dungeons", platform="Minecraft", code="frostkeep.test:25565", description="Class-based dungeon runs with keys, bosses, loot routes, and weekly modifiers.", genre="Dungeon", party=5, minutes=50, difficulty="Intermediate", active=497, verified=1, owner="creator", badge="Popular", version="Raid 6", hours=8),

    # GTA V FiveM
    dict(name="Pacific Response RP", platform="GTA V FiveM", code="connect.pacificresponse.test", description="Coordinated police, medical, and civilian roleplay scenarios with scheduled shifts.", genre="Roleplay", party=16, minutes=90, difficulty="Intermediate", active=832, verified=1, owner="admin", badge="Popular", version="Season 6", hours=4),
    dict(name="Canyon Drift Union", platform="GTA V FiveM", code="driftunion.test", description="Tandem drift lobbies, judged team runs, custom cars, and mountain pass events.", genre="Racing", party=12, minutes=45, difficulty="Advanced", active=446, verified=0, owner="creator", badge="Rising", version="Touge 2", hours=10),
    dict(name="Night Freight Convoys", platform="GTA V FiveM", code="nightfreight.test", description="Plan long-haul trucking convoys with escorts, fuel stops, and delivery contracts.", genre="Simulation", party=10, minutes=60, difficulty="Casual", active=278, verified=0, owner="admin", badge="Community", version="Route Pack 5", hours=19),
    dict(name="Vaultbreak Crew Jobs", platform="GTA V FiveM", code="vaultbreak.test", description="Four-stage cooperative heists where every player has a specialist role.", genre="Heist", party=6, minutes=55, difficulty="Advanced", active=719, verified=1, owner="creator", badge="Featured", version="Job 11", hours=6),

    # Halo Infinite Forge
    dict(name="Banished Boarding Action", platform="Halo Infinite Forge", code="HI-BBA-7021", description="Breach a moving warship through scripted rooms, objectives, and boss encounters.", genre="Campaign", party=4, minutes=35, difficulty="Intermediate", active=521, verified=1, owner="creator", badge="Featured", version="v2.1", hours=11),
    dict(name="Gravity Gridball", platform="Halo Infinite Forge", code="HI-GGB-4418", description="Zero-gravity team sport with passes, launch pads, and rotating scoring gates.", genre="Sports", party=8, minutes=18, difficulty="Competitive", active=693, verified=0, owner="creator", badge="Hot", version="League 1", hours=5),
    dict(name="Spartan Tower Defense", platform="Halo Infinite Forge", code="HI-STD-9034", description="Defend power cores, purchase upgrades, and coordinate lanes against escalating waves.", genre="Defense", party=6, minutes=30, difficulty="Intermediate", active=388, verified=0, owner="admin", badge="Trending", version="Wave 20", hours=16),
    dict(name="Forerunner Puzzle Vault", platform="Halo Infinite Forge", code="HI-FPV-3380", description="A cooperative logic maze using switches, vehicles, physics, and synchronized movement.", genre="Puzzle", party=4, minutes=28, difficulty="Advanced", active=245, verified=1, owner="creator", badge="Challenge", version="v1.9", hours=20),

    # Fall Guys Creative
    dict(name="Hexa Harbor Sprint", platform="Fall Guys Creative", code="FG-1184-5520", description="Race through disappearing docks, swinging cranes, and team-operated shortcuts.", genre="Race", party=12, minutes=10, difficulty="Beginner", active=980, verified=1, owner="creator", badge="Trending", version="Round 4", hours=4),
    dict(name="Skyhook Survival", platform="Fall Guys Creative", code="FG-7042-1198", description="Stay on a rotating airship while hooks, fans, and collapsing tiles reshape the arena.", genre="Survival", party=16, minutes=12, difficulty="Intermediate", active=774, verified=0, owner="creator", badge="Hot", version="v2.0", hours=9),
    dict(name="Beanball Arena", platform="Fall Guys Creative", code="FG-4410-8836", description="A fast team ball mode with launch ramps, moving goals, and overtime hazards.", genre="Sports", party=10, minutes=9, difficulty="Competitive", active=615, verified=0, owner="admin", badge="Popular", version="Cup 3", hours=15),
    dict(name="Co-op Castle Climb", platform="Fall Guys Creative", code="FG-9081-3374", description="Pairs open gates for each other while climbing a vertical obstacle castle.", genre="Co-op", party=8, minutes=14, difficulty="Intermediate", active=536, verified=1, owner="creator", badge="Rising", version="v1.5", hours=13),

    # Rec Room
    dict(name="Clockwork Manor Escape", platform="Rec Room", code="RR-CLOCKWORK-27", description="Voice-friendly escape room with mechanical clues and four-player role puzzles.", genre="Escape Room", party=4, minutes=45, difficulty="Advanced", active=327, verified=1, owner="creator", badge="Featured", version="Act 2", hours=7),
    dict(name="Laser League Academy", platform="Rec Room", code="RR-LASER-501", description="Team training drills lead into competitive laser-tag rounds and ranked scrims.", genre="PvP", party=8, minutes=25, difficulty="Competitive", active=469, verified=0, owner="admin", badge="Community", version="Season 9", hours=12),
    dict(name="Quest for Emberdeep", platform="Rec Room", code="RR-EMBER-884", description="Dungeon quest with tank, support, and damage roles across branching encounters.", genre="Quest", party=5, minutes=50, difficulty="Intermediate", active=591, verified=1, owner="creator", badge="Popular", version="Chapter 5", hours=6),
    dict(name="Mini Golf Moonbase", platform="Rec Room", code="RR-MOONGOLF-16", description="Social mini golf across low-gravity labs with team challenges and trick shots.", genre="Social", party=8, minutes=30, difficulty="Casual", active=283, verified=0, owner="admin", badge="Chill", version="Course 2", hours=21),

    # VRChat
    dict(name="Orbital Mystery Club", platform="VRChat", code="wrld_orbital_mystery_demo", description="Social deduction aboard a space station with tasks, evidence, and timed meetings.", genre="Social Deduction", party=10, minutes=35, difficulty="Intermediate", active=704, verified=1, owner="creator", badge="Trending", version="v3.2", hours=5),
    dict(name="The Endless Library", platform="VRChat", code="wrld_endless_library_demo", description="Explore shifting rooms, solve lore puzzles, and record routes with a small team.", genre="Exploration", party=6, minutes=45, difficulty="Advanced", active=418, verified=0, owner="creator", badge="Featured", version="Volume 7", hours=10),
    dict(name="Neon Rhythm Rooftops", platform="VRChat", code="wrld_neon_rhythm_demo", description="Multiplayer rhythm challenges, dance battles, and synchronized rooftop stages.", genre="Rhythm", party=12, minutes=25, difficulty="Casual", active=856, verified=1, owner="admin", badge="Hot", version="Mix 12", hours=3),
    dict(name="Cozy Campfire Stories", platform="VRChat", code="wrld_cozy_campfire_demo", description="A moderated social world for storytelling circles, mini-games, and community nights.", genre="Social", party=16, minutes=60, difficulty="Casual", active=389, verified=0, owner="admin", badge="Community", version="Autumn", hours=18),

    # Core Games
    dict(name="Crystal Siege Online", platform="Core Games", code="CORE-CRYSTAL-441", description="Capture crystal lanes, upgrade defenses, and coordinate hero abilities in team battles.", genre="MOBA", party=10, minutes=28, difficulty="Competitive", active=612, verified=1, owner="creator", badge="Featured", version="Season 4", hours=8),
    dict(name="Dungeon Architect Co-op", platform="Core Games", code="CORE-DUNGEON-390", description="Build a dungeon together, then defend it from rival adventuring teams.", genre="Builder", party=8, minutes=40, difficulty="Intermediate", active=374, verified=0, owner="creator", badge="Rising", version="Blueprint 6", hours=13),
    dict(name="Aero Circuit Racers", platform="Core Games", code="CORE-AERO-118", description="High-speed hovercraft racing with team drafting, boosts, and custom tracks.", genre="Racing", party=12, minutes=20, difficulty="Intermediate", active=498, verified=0, owner="admin", badge="Popular", version="Cup 8", hours=17),
    dict(name="Outpost Omega Survival", platform="Core Games", code="CORE-OMEGA-772", description="Gather resources by day and defend a shared sci-fi outpost through the night.", genre="Survival", party=6, minutes=45, difficulty="Advanced", active=541, verified=1, owner="creator", badge="Trending", version="Night 10", hours=6),

    # Garry's Mod
    dict(name="Metro Incident Roleplay", platform="Garry's Mod", code="gmod.metroincident.test:27015", description="Structured emergency roleplay in a dense metro system with rotating incidents.", genre="Roleplay", party=16, minutes=75, difficulty="Intermediate", active=431, verified=0, owner="admin", badge="Community", version="Build 42", hours=14),
    dict(name="Prop Hunt: Museum After Dark", platform="Garry's Mod", code="gmod.museumhunt.test:27015", description="Hunters search a large museum while props coordinate distractions and hiding routes.", genre="Prop Hunt", party=12, minutes=18, difficulty="Casual", active=702, verified=1, owner="creator", badge="Popular", version="Wing 3", hours=7),
    dict(name="Trouble at Polar Station", platform="Garry's Mod", code="gmod.polarstation.test:27015", description="Social deduction with environmental hazards, locked labs, and role objectives.", genre="TTT", party=14, minutes=22, difficulty="Intermediate", active=633, verified=0, owner="creator", badge="Hot", version="v4.8", hours=5),
    dict(name="Physics Factory Challenge", platform="Garry's Mod", code="gmod.physicsfactory.test:27015", description="Teams construct machines to solve transport, launch, and destruction challenges.", genre="Sandbox", party=8, minutes=35, difficulty="Advanced", active=296, verified=1, owner="admin", badge="Challenge", version="Trial 9", hours=19),

    # Counter-Strike 2 Workshop
    dict(name="Co-op Breach: Blacksite", platform="Counter-Strike 2 Workshop", code="CS2-WS-BLACKSITE-44", description="A scripted cooperative assault with objectives, checkpoints, and specialist loadouts.", genre="Co-op", party=5, minutes=35, difficulty="Advanced", active=583, verified=1, owner="creator", badge="Featured", version="v2.6", hours=6),
    dict(name="Retake Lab: Mirage Variants", platform="Counter-Strike 2 Workshop", code="CS2-WS-RETAKE-18", description="Fast retake scenarios with randomized utility, positions, and team assignments.", genre="Training", party=10, minutes=20, difficulty="Competitive", active=1044, verified=1, owner="creator", badge="Hot", version="Pack 7", hours=3),
    dict(name="KZ Skyline Marathon", platform="Counter-Strike 2 Workshop", code="CS2-WS-KZ-701", description="A long cooperative climb with checkpoints, route coaching, and time targets.", genre="KZ", party=8, minutes=45, difficulty="Advanced", active=472, verified=0, owner="admin", badge="Challenge", version="v1.4", hours=11),
    dict(name="Hideout Arms Race", platform="Counter-Strike 2 Workshop", code="CS2-WS-ARMS-330", description="Compact vertical arms-race arena built for quick parties and rotating weapon ladders.", genre="Arms Race", party=12, minutes=15, difficulty="Casual", active=658, verified=0, owner="creator", badge="Popular", version="v3.1", hours=16),

    # Trackmania
    dict(name="Neon Coast Team Relay", platform="Trackmania", code="TM-NEONCOAST-2026", description="Four-leg team relay where clean handoffs and consistent pace beat raw speed.", genre="Relay", party=8, minutes=25, difficulty="Intermediate", active=524, verified=1, owner="creator", badge="Featured", version="Campaign 2", hours=8),
    dict(name="Ice Reactor Trials", platform="Trackmania", code="TM-ICEREACTOR-77", description="Technical ice tracks with practice groups, route coaching, and medal attempts.", genre="Time Attack", party=10, minutes=30, difficulty="Advanced", active=611, verified=0, owner="admin", badge="Challenge", version="Pack 5", hours=12),
    dict(name="Desert Duo Cup", platform="Trackmania", code="TM-DESERTDUO-14", description="Short duo races where partners alternate qualification and knockout rounds.", genre="Tournament", party=8, minutes=35, difficulty="Competitive", active=458, verified=1, owner="creator", badge="Trending", version="Cup 4", hours=5),
    dict(name="Beginner Tech School", platform="Trackmania", code="TM-TECHSCHOOL-101", description="Guided training maps for gears, drifts, speed slides, and consistent finishes.", genre="Training", party=12, minutes=25, difficulty="Beginner", active=736, verified=0, owner="admin", badge="Learning", version="Lesson 12", hours=9),
]
