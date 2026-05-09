"""Generate a standard static table asset in Blender.

Run from Blender Python through the live MCP bridge. The script is repeatable:
it creates the source scene, exports a static GLB, renders a preview, and
writes metadata for the Artomata viewer.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
    add_bevel,
    add_weighted_normals,
    bounds_for_objects,
    clear_scene,
    collection,
    cone,
    cube,
    cylinder,
    ensure_dir,
    look_at,
    make_mat,
    scene_triangle_count,
    write_json,
)

ASSET_SLUG = "table"
ASSET_NAME = "Table"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Furniture",
    "subject": "Standard rectangular table",
    "visual_style": "Clean procedural studio furniture with softened edges and visible wood detail",
    "required_parts": ["Tabletop", "apron rails", "four legs", "foot caps", "contact shadow"],
    "material_palette": [
        "warm walnut tabletop and legs",
        "darker endgrain bands",
        "muted slate underside and foot caps",
        "soft translucent contact shadow",
    ],
    "rig_target": "none",
    "animation_clips": [],
    "viewer_framing": "front-quarter view, slightly above tabletop, centered on full table footprint",
}


def repo_root() -> Path:
    return SCRIPT_DIR.parents[1]


def relative(path: str | Path) -> str:
    return str(Path(path).relative_to(repo_root())).replace("\\", "/")


def out_paths() -> dict[str, Path]:
    root = repo_root()
    return {
        "blend": root / "public" / "models" / f"{ASSET_SLUG}.blend",
        "glb": root / "public" / "models" / f"{ASSET_SLUG}.glb",
        "preview": root / "public" / "renders" / f"{ASSET_SLUG}-preview.png",
        "metadata": root / "public" / "models" / f"{ASSET_SLUG}.metadata.json",
        "textures": root / "public" / "textures" / ASSET_SLUG,
    }


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "walnut": make_mat("MAT_Table_WarmWalnut", (0.47, 0.25, 0.115, 1), roughness=0.58),
        "endgrain": make_mat("MAT_Table_DarkEndgrain", (0.24, 0.12, 0.055, 1), roughness=0.72),
        "slate": make_mat("MAT_Table_MutedSlateFeet", (0.115, 0.13, 0.145, 1), roughness=0.7, metallic=0.12),
        "underside": make_mat("MAT_Table_SatinUnderside", (0.18, 0.14, 0.105, 1), roughness=0.66),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.54), roughness=0.92, alpha=0.54),
    }


def operator_kwargs(operator, kwargs: dict) -> dict:
    accepted = {prop.identifier for prop in operator.get_rna_type().properties if not prop.is_readonly}
    return {key: value for key, value in kwargs.items() if key in accepted}


def run_operator(operator, **kwargs):
    return operator(**operator_kwargs(operator, kwargs))


def select_objects(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "MESH"]


def geometry_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type in {"MESH", "CURVE"}]


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def clear_animation_data() -> None:
    for obj in bpy.data.objects:
        obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def softened_table_leg(
    name: str,
    loc: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
) -> list[bpy.types.Object]:
    leg = cone(
        name,
        loc,
        0.038,
        0.056,
        0.68,
        mats["walnut"],
        vertices=20,
        collection_name="PROPS",
    )
    add_bevel(leg, 0.007, 2, apply=True)
    add_weighted_normals(leg)

    cap = cylinder(
        f"{name}_SlateFootCap",
        (loc[0], loc[1], 0.018),
        0.049,
        0.034,
        mats["slate"],
        vertices=24,
        bevel=0.004,
        collection_name="PROPS",
    )
    return [leg, cap]


def build_table(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    # Tabletop, softened rim, and underside support.
    add(cube("PROP_Table_Tabletop_BeveledWalnutSlab", (0, 0, 0.75), (0.72, 0.4, 0.055), mats["walnut"], bevel=0.032, collection_name="PROPS"))
    add(cube("PROP_Table_Underside_SatinSupportPlate", (0, 0, 0.685), (0.55, 0.27, 0.032), mats["underside"], bevel=0.016, collection_name="PROPS"))
    add(cube("PROP_Table_FrontDarkEndgrainBand", (0, -0.418, 0.735), (0.72, 0.024, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))
    add(cube("PROP_Table_BackDarkEndgrainBand", (0, 0.418, 0.735), (0.72, 0.024, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))
    add(cube("PROP_Table_LeftDarkEndgrainBand", (-0.738, 0, 0.735), (0.024, 0.4, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))
    add(cube("PROP_Table_RightDarkEndgrainBand", (0.738, 0, 0.735), (0.024, 0.4, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))

    # Apron rails.
    add(cube("PROP_Table_FrontApronRail", (0, -0.315, 0.645), (0.5, 0.036, 0.06), mats["walnut"], bevel=0.011, collection_name="PROPS"))
    add(cube("PROP_Table_BackApronRail", (0, 0.315, 0.645), (0.5, 0.036, 0.06), mats["walnut"], bevel=0.011, collection_name="PROPS"))
    add(cube("PROP_Table_LeftSideApronRail", (-0.53, 0, 0.645), (0.036, 0.265, 0.06), mats["walnut"], bevel=0.011, collection_name="PROPS"))
    add(cube("PROP_Table_RightSideApronRail", (0.53, 0, 0.645), (0.036, 0.265, 0.06), mats["walnut"], bevel=0.011, collection_name="PROPS"))

    # Legs and foot stretchers.
    for side_name, x in [("Left", -0.52), ("Right", 0.52)]:
        for row_name, y in [("Front", -0.29), ("Back", 0.29)]:
            objects.extend(softened_table_leg(f"PROP_Table_{row_name}{side_name}_TaperedWalnutLeg", (x, y, 0.34), mats))

    add(cylinder("BASE_BakedSoftContactShadow", (0, 0, 0.004), 0.52, 0.008, mats["shadow"], vertices=72, scale=(1.35, 0.88, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.026, 0.031, 0.034)

    camera_data = bpy.data.cameras.new("CAM_Table_Preview")
    camera = bpy.data.objects.new("CAM_Table_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (1.72, -2.42, 1.18)
    camera.data.lens = 54
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 2.9
    camera.data.dof.aperture_fstop = 7.0
    look_at(camera, (0, 0.02, 0.48))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_TableSoftbox", "AREA", (-2.4, -2.8, 2.8), 430, 3.5),
        ("LGT_Rim_TableTopEdge", "AREA", (2.1, 1.55, 1.75), 145, 1.8),
        ("LGT_Fill_TableStudio", "POINT", (1.25, -1.6, 1.15), 68, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0.02, 0.48))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_StandardTable"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 1
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 64


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def export_glb(path: Path, objects: list[bpy.types.Object]) -> None:
    ensure_dir(path.parent)
    select_objects(objects)
    run_operator(
        bpy.ops.export_scene.gltf,
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
    )


def export_asset(paths: dict[str, Path]) -> None:
    ensure_dir(paths["blend"].parent)
    ensure_dir(paths["glb"].parent)
    ensure_dir(paths["preview"].parent)
    ensure_dir(paths["textures"])

    for block in (bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], geometry_objects())

    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)


def collect_metadata(paths: dict[str, Path]) -> dict:
    meshes = mesh_objects()
    geometries = geometry_objects()
    actions = sorted(action.name for action in bpy.data.actions)
    return {
        "asset": ASSET_NAME,
        "slug": ASSET_SLUG,
        "generator": Path(__file__).name,
        "spec": ASSET_SPEC,
        "paths": {
            "blend": relative(paths["blend"]),
            "glb": relative(paths["glb"]),
            "preview": relative(paths["preview"]),
            "metadata": relative(paths["metadata"]),
        },
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len(meshes),
            "geometry_objects": len(geometries),
            "materials": len(material_names(geometries)),
            "triangles": scene_triangle_count(geometries),
            "bones": 0,
            "animations": len(actions),
        },
        "materials": material_names(geometries),
        "animations": {
            "clips": actions,
            "default": None,
            "embedded_in_glb": False,
        },
        "bounds": bounds_for_objects(geometries),
        "budgets": {
            "triangle_warning": 100000,
            "glb_size_warning_bytes": 12 * 1024 * 1024,
            "material_warning": 16,
        },
        "file_sizes": {
            "blend_bytes": file_size(paths["blend"]),
            "glb_bytes": file_size(paths["glb"]),
            "preview_bytes": file_size(paths["preview"]),
        },
        "export": {
            "format": "GLB",
            "export_yup": True,
            "applied_export_transforms": True,
            "animations": False,
            "source": "Blender MCP live bridge",
        },
        "notes": [
            "Standard rectangular table generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Chosen palette: warm walnut frame, darker endgrain bands, muted slate foot caps, and baked contact shadow.",
        ],
    }


def main() -> dict:
    paths = out_paths()
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    clear_scene()
    clear_animation_data()
    configure_scene()
    mats = make_materials()
    build_table(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
