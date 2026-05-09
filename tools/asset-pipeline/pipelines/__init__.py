"""Reusable OnTheSpectrum asset family pipelines."""

from __future__ import annotations

from . import character, furniture, plant, prop, vfx

PIPELINE_MODULES = {
    "character.humanoid_basic": character,
    "character.chibi_mascot": character,
    "furniture.static_or_mechanical": furniture,
    "plant.swaying_botanical": plant,
    "prop.static_or_turntable": prop,
    "vfx.baked_mesh_curve": vfx,
}


def run_asset_pipeline(spec: dict) -> dict:
    pipeline_id = spec.get("pipelineId")
    module = PIPELINE_MODULES.get(pipeline_id)
    if module is None:
        raise ValueError(f"Unsupported OnTheSpectrum pipelineId: {pipeline_id}")
    return module.generate(spec)
