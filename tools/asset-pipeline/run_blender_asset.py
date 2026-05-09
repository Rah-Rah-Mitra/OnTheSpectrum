"""Run a Blender asset script in background Blender when BLENDER_PATH is set.

The live MCP bridge is preferred by Codex. This helper exists for repeatable
local runs outside the chat environment.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", default="tools/asset-pipeline/create_artomata_painter_chibi.py")
    parser.add_argument("--blend-file", default="")
    args = parser.parse_args()

    blender = os.environ.get("BLENDER_PATH") or "blender"
    script = Path(args.script).resolve()
    command = [blender, "--background"]
    if args.blend_file:
        command.append(str(Path(args.blend_file).resolve()))
    command.extend(["--python", str(script)])
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
