from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from pathlib import Path

from dotenv import dotenv_values

APP_NAME = "SquadFinder"
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.env"


def _env_quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def _show_error(title: str, message: str) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


def _ask_retry(message: str) -> bool:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askyesno(
        "SquadFinder",
        message + "\n\nDo you want to re-enter your Supabase settings?",
    )
    root.destroy()
    return bool(answer)


def _setup_window() -> bool:
    import tkinter as tk
    from tkinter import messagebox

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.title("SquadFinder Setup")
    root.geometry("760x455")
    root.minsize(700, 420)

    frame = tk.Frame(root, padx=24, pady=22)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Welcome to SquadFinder",
        font=("Segoe UI", 20, "bold"),
    ).pack(anchor="w")

    tk.Label(
        frame,
        text="Connect your own Supabase database. These settings stay on this Windows PC.",
        font=("Segoe UI", 10),
    ).pack(anchor="w", pady=(4, 18))

    tk.Label(
        frame,
        text="Supabase Session Pooler Database URL",
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")

    db_var = tk.StringVar()
    db_entry = tk.Entry(frame, textvariable=db_var, font=("Consolas", 10))
    db_entry.pack(fill="x", pady=(5, 8))

    tk.Label(
        frame,
        text=(
            "In Supabase: Connect → Session pooler. "
            "Paste the PostgreSQL connection string here. "
            "Do not use the anon/publishable key."
        ),
        wraplength=700,
        justify="left",
        fg="#555",
    ).pack(anchor="w", pady=(0, 18))

    admin_frame = tk.LabelFrame(
        frame,
        text="Optional administrator account",
        padx=12,
        pady=10,
    )
    admin_frame.pack(fill="x")

    admin_user = tk.StringVar(value="admin")
    admin_email = tk.StringVar()
    admin_password = tk.StringVar()

    tk.Label(admin_frame, text="Username").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    tk.Entry(admin_frame, textvariable=admin_user).grid(row=0, column=1, sticky="ew", pady=4)

    tk.Label(admin_frame, text="Email").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    tk.Entry(admin_frame, textvariable=admin_email).grid(row=1, column=1, sticky="ew", pady=4)

    tk.Label(admin_frame, text="Password").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    tk.Entry(admin_frame, textvariable=admin_password, show="*").grid(row=2, column=1, sticky="ew", pady=4)

    admin_frame.columnconfigure(1, weight=1)
    result = {"saved": False}

    def save_and_close() -> None:
        db_url = db_var.get().strip()

        if not db_url.startswith(("postgresql://", "postgres://")):
            messagebox.showerror(
                "Invalid database URL",
                "Paste the PostgreSQL Session Pooler URL from Supabase.",
            )
            return

        lines = [
            f"SUPABASE_DB_URL={_env_quote(db_url)}",
            f"SQUADFINDER_SECRET_KEY={_env_quote(secrets.token_urlsafe(48))}",
            "SQUADFINDER_CLOUD=0",
            "SQUADFINDER_SEED_DEMO=0",
            "SQUADFINDER_SEED_CATALOG=0",
            "SQUADFINDER_HSTS=0",
            "SQUADFINDER_FORCE_HTTPS=0",
            "SQUADFINDER_HTTPS=0",
        ]

        if admin_user.get().strip():
            lines.append(
                f"SQUADFINDER_ADMIN_USERNAME={_env_quote(admin_user.get().strip())}"
            )
        if admin_email.get().strip():
            lines.append(
                f"SQUADFINDER_ADMIN_EMAIL={_env_quote(admin_email.get().strip())}"
            )
        if admin_password.get():
            lines.append(
                f"SQUADFINDER_ADMIN_PASSWORD={_env_quote(admin_password.get())}"
            )

        CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result["saved"] = True
        root.destroy()

    button_row = tk.Frame(frame)
    button_row.pack(fill="x", pady=(18, 0))

    tk.Button(
        button_row,
        text="Save & Start SquadFinder",
        command=save_and_close,
        padx=16,
        pady=8,
    ).pack(side="right")

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    db_entry.focus_set()
    root.mainloop()

    return bool(result["saved"])


def _load_config() -> bool:
    if not CONFIG_FILE.exists():
        if not _setup_window():
            return False

    values = dotenv_values(CONFIG_FILE)
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value

    # Supabase is remote, but the desktop UI itself is local HTTP.
    # Keep cloud mode off so secure-cookie rules do not break local login.
    os.environ["SQUADFINDER_CLOUD"] = "0"
    os.environ["SQUADFINDER_SEED_DEMO"] = "0"
    os.environ["SQUADFINDER_SEED_CATALOG"] = "0"
    os.environ["SQUADFINDER_HSTS"] = "0"
    os.environ["SQUADFINDER_FORCE_HTTPS"] = "0"
    os.environ["SQUADFINDER_HTTPS"] = "0"

    return bool(os.environ.get("SUPABASE_DB_URL"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _run_once() -> int:
    if not _load_config():
        return 0

    # app.py reads the environment during import, so import it only after setup.
    from app import app
    from waitress import serve
    import webview

    port = _free_port()

    def run_server() -> None:
        serve(
            app,
            host="127.0.0.1",
            port=port,
            threads=8,
            url_scheme="http",
        )

    server_thread = threading.Thread(
        target=run_server,
        name="SquadFinderServer",
        daemon=True,
    )
    server_thread.start()

    if not _wait_for_server(port):
        raise RuntimeError("The local SquadFinder server did not start.")

    webview.create_window(
        "SquadFinder",
        f"http://127.0.0.1:{port}/",
        width=1440,
        height=900,
        min_size=(980, 650),
        resizable=True,
    )
    webview.start(debug=False)
    return 0


def main() -> int:
    try:
        return _run_once()
    except Exception as exc:
        try:
            retry = _ask_retry(f"SquadFinder could not start.\n\n{exc}")
        except Exception:
            _show_error("SquadFinder Error", f"SquadFinder could not start.\n\n{exc}")
            retry = False

        if retry:
            try:
                CONFIG_FILE.unlink(missing_ok=True)
            except Exception:
                pass

            # Clear the values that app.py reads during import on the next process.
            _show_error(
                "SquadFinder",
                "Your saved settings were cleared.\n\nClose SquadFinder and open it again to enter new Supabase settings.",
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
