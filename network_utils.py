"""Network helpers: detect LAN IP, check Bonjour service, check port availability."""
from __future__ import annotations

import socket
import subprocess


def get_lan_ip() -> str:
    """Return the primary LAN IPv4 address used to reach the local network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def bonjour_running() -> bool:
    """Apple's Bonjour Service must be running for AirPlay discovery on Windows."""
    try:
        out = subprocess.run(
            ["sc", "query", "Bonjour Service"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return "RUNNING" in out.stdout.upper()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def try_start_bonjour() -> bool:
    """Attempt to start Bonjour Service. Requires admin; returns True on success."""
    try:
        r = subprocess.run(
            ["net", "start", "Bonjour Service"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return r.returncode == 0 or bonjour_running()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
