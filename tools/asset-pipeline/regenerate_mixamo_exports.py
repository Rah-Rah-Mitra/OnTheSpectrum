"""Regenerate existing humanoid Mixamo upload exports only.

This opens the committed Blender source scenes and rewrites the Mixamo FBX and
OBJ ZIP files without touching the web GLBs, preview renders, or source blends.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import add_mixamo_exports_and_animations as chibi_pipeline  # noqa: E402
import create_toon_blaster_runner as toon_pipeline  # noqa: E402


ORIENTATION_NOTE = chibi_pipeline.MIXAMO_ORIENTATION_NOTE


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def update_metadata(metadata_path: Path, mixamo_fbx: Path, mixamo_obj_zip: Path) -> None:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    notes = data.setdefault("notes", [])
    if ORIENTATION_NOTE not in notes:
        insert_at = max(0, len(notes) - 1)
        notes.insert(insert_at, ORIENTATION_NOTE)

    file_sizes = data.setdefault("file_sizes", {})
    file_sizes["mixamo_fbx_bytes"] = file_size(mixamo_fbx)
    file_sizes["mixamo_obj_zip_bytes"] = file_size(mixamo_obj_zip)
    metadata_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def regenerate_chibi() -> dict[str, str]:
    paths = chibi_pipeline.paths_for(chibi_pipeline.CHIBI_SLUG)
    bpy.ops.wm.open_mainfile(filepath=str(paths["blend"]))
    mixamo = chibi_pipeline.mixamo_objects()
    chibi_pipeline.export_mixamo_fbx(paths["mixamo_fbx"], mixamo)
    chibi_pipeline.export_mixamo_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], mixamo)
    update_metadata(paths["metadata"], paths["mixamo_fbx"], paths["mixamo_obj_zip"])
    return {
        "mixamo_fbx": chibi_pipeline.relative(paths["mixamo_fbx"]),
        "mixamo_obj_zip": chibi_pipeline.relative(paths["mixamo_obj_zip"]),
    }


def regenerate_toon_blaster_runner() -> dict[str, str]:
    paths = toon_pipeline.out_paths()
    bpy.ops.wm.open_mainfile(filepath=str(paths["blend"]))
    mixamo = toon_pipeline.mixamo_objects()
    toon_pipeline.export_mixamo_fbx(paths["mixamo_fbx"], mixamo)
    toon_pipeline.export_mixamo_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], mixamo)
    update_metadata(paths["metadata"], paths["mixamo_fbx"], paths["mixamo_obj_zip"])
    return {
        "mixamo_fbx": toon_pipeline.relative(paths["mixamo_fbx"]),
        "mixamo_obj_zip": toon_pipeline.relative(paths["mixamo_obj_zip"]),
    }


def main() -> dict[str, dict[str, str]]:
    return {
        "on_the_spectrum-painter-chibi": regenerate_chibi(),
        "toon-blaster-runner": regenerate_toon_blaster_runner(),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
