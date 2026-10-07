SquadFinder Windows EXE Builder
================================

Purpose
-------
This package creates a real Windows SquadFinder.exe from the current public
GitHub repository:
https://github.com/Jad-Programmer/SquadFinder

What the finished EXE does
--------------------------
- Opens SquadFinder in its own desktop window (no browser address bar).
- Starts the Flask app internally on 127.0.0.1.
- On first launch, asks the user for THEIR OWN Supabase Session Pooler
  PostgreSQL URL.
- Saves that user's configuration locally in:
  %LOCALAPPDATA%\SquadFinder\config.env
- Does not contain Jad's Supabase password or private database URL.

How to build
------------
1. Extract this ZIP on a Windows PC.
2. Double-click BUILD_SQUADFINDER_EXE.bat.
3. Wait while it downloads the current GitHub source and installs build tools.
4. When finished, SquadFinder.exe will appear beside the BAT file.

Requirement
-----------
Python 3.13 for Windows must be installed. The builder will tell you if it is
missing.

Important
---------
The resulting EXE is unsigned. Windows SmartScreen may display an "Unknown
publisher" warning. That is normal for a locally-built unsigned PyInstaller
application.

The build process downloads packages from PyPI and the source from GitHub, so
the Windows PC needs an internet connection while building.
