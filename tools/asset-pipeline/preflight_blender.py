"""Check whether Blender asset generation can run on this machine."""

from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path


def check_socket(host: str = "127.0.0.1", port: int = 9876, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    blender_path = os.environ.get("BLENDER_PATH")
    blender_on_path = shutil.which("blender")
    launcher = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "blender-launcher.exe"
    report = {
        "mcp_bridge": {
            "host": "127.0.0.1",
            "port": 9876,
            "listening": check_socket(),
        },
        "background_blender": {
            "BLENDER_PATH": blender_path,
            "blender_on_path": blender_on_path,
            "windows_store_launcher": str(launcher) if launcher.exists() else None,
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if report["mcp_bridge"]["listening"] or blender_path or blender_on_path else 2


if __name__ == "__main__":
    raise SystemExit(main())
