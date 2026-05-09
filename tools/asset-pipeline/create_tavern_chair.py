"""Generate a stylized fantasy tavern chair asset in Blender.

Run from Blender Python through the live MCP bridge when available, or through
background Blender via run_blender_asset.py. The script is repeatable: it
creates the source scene, exports a static GLB, renders a preview, and writes
metadata for the OnTheSpectrum viewer.
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
    bevel_curve,
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

ASSET_SLUG = "tavern-chair"
ASSET_NAME = "Tavern Chair"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Furniture",
    "subject": "Tavern chair",
    "visual_style": "Stylized fantasy inn furniture with chunky handcrafted proportions",
    "required_parts": [
        "wooden seat",
        "backrest",
        "four legs",
        "cross braces",
        "small carved details",
        "contact shadow",
    ],
    "material_palette": [
        "warm brown wood",
        "darker edge wear",
        "subtle geometric grain lines",
        "soft translucent contact shadow",
    ],
    "rig_target": "none",
    "animation_clips": [],
    "viewer_framing": "3/4 view from slightly above, chair fully visible, readable seat and backrest",
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
        "wood": make_mat("MAT_TavernChair_WarmBrownWood", (0.55, 0.29, 0.12, 1), roughness=0.66),
        "edge": make_mat("MAT_TavernChair_DarkEdgeWear", (0.25, 0.12, 0.045, 1), roughness=0.82),
        "grain": make_mat("MAT_TavernChair_GrainLines", (0.16, 0.08, 0.034, 1), roughness=0.88),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.019, 0.021, 0.54), roughness=0.94, alpha=0.54),
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


def add_rotated_cube(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    rotation: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    bevel: float = 0.012,
    collection_name: str = "PROPS",
) -> bpy.types.Object:
    obj = cube(name, loc, scale, mat, bevel=bevel, collection_name=collection_name)
    obj.rotation_euler = rotation
    return obj


def add_leg(name: str, loc: tuple[float, float, float], mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    leg = cone(
        name,
        loc,
        0.046,
        0.067,
        0.48,
        mats["wood"],
        vertices=18,
        collection_name="PROPS",
    )
    add_bevel(leg, 0.007, 2, apply=True)
    add_weighted_normals(leg)

    foot = cylinder(
        f"{name}_DarkWornFoot",
        (loc[0], loc[1], 0.028),
        0.055,
        0.04,
        mats["edge"],
        vertices=18,
        bevel=0.006,
        collection_name="PROPS",
    )
    return [leg, foot]


def add_seat_grain(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    top_z = 0.57
    grain_paths = [
        [(-0.29, -0.19, top_z), (-0.1, -0.215, top_z + 0.002), (0.25, -0.195, top_z)],
        [(-0.31, -0.06, top_z), (-0.05, -0.04, top_z + 0.002), (0.31, -0.07, top_z)],
        [(-0.25, 0.08, top_z), (-0.02, 0.1, top_z + 0.002), (0.26, 0.075, top_z)],
        [(-0.22, 0.22, top_z), (0.04, 0.19, top_z + 0.002), (0.29, 0.215, top_z)],
    ]
    for index, points in enumerate(grain_paths, start=1):
        objects.append(
            bevel_curve(
                f"PROP_TavernChair_Seat_GrainLine_{index:02d}",
                points,
                mats["grain"],
                bevel_depth=0.0032,
                bevel_resolution=1,
                resolution=8,
                collection_name="PROPS",
            )
        )

    seam_specs = [(-0.125, "Left"), (0.125, "Right")]
    for x, label in seam_specs:
        objects.append(
            bevel_curve(
                f"PROP_TavernChair_Seat_{label}PlankSeam",
                [(x, -0.275, top_z + 0.001), (x + 0.012, 0.27, top_z + 0.001)],
                mats["edge"],
                bevel_depth=0.004,
                bevel_resolution=1,
                resolution=4,
                collection_name="PROPS",
            )
        )

    return objects


def add_backrest_carving(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    y = 0.305
    carving_paths = [
        [(-0.25, y, 1.015), (-0.1, y - 0.01, 1.05), (0.0, y, 1.02), (0.1, y - 0.01, 1.05), (0.25, y, 1.015)],
        [(-0.22, y - 0.002, 0.86), (-0.04, y - 0.012, 0.885), (0.22, y - 0.002, 0.86)],
        [(-0.2, y - 0.002, 0.76), (-0.02, y - 0.014, 0.78), (0.19, y - 0.002, 0.755)],
    ]
    for index, points in enumerate(carving_paths, start=1):
        objects.append(
            bevel_curve(
                f"PROP_TavernChair_Backrest_CarvedLine_{index:02d}",
                points,
                mats["grain"],
                bevel_depth=0.0042,
                bevel_resolution=1,
                resolution=12,
                collection_name="PROPS",
            )
        )

    for index, x in enumerate([-0.245, 0.245], start=1):
        objects.append(
            cylinder(
                f"PROP_TavernChair_Backrest_RoundPeg_{index:02d}",
                (x, y - 0.018, 0.91),
                0.028,
                0.018,
                mats["edge"],
                vertices=20,
                rotation=(math.radians(90), 0, 0),
                bevel=0.004,
                collection_name="PROPS",
            )
        )

    return objects


def build_tavern_chair(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    # Three chunky seat planks with darker worn lips.
    plank_specs = [
        ("Left", -0.245, math.radians(0.9)),
        ("Center", 0.0, math.radians(-0.4)),
        ("Right", 0.245, math.radians(0.7)),
    ]
    for label, x, rot_z in plank_specs:
        add(
            add_rotated_cube(
                f"PROP_TavernChair_Seat_{label}HandhewnPlank",
                (x, 0, 0.52),
                (0.232, 0.56, 0.085),
                (0, 0, rot_z),
                mats["wood"],
                bevel=0.026,
            )
        )

    add(cube("PROP_TavernChair_Seat_FrontDarkWornLip", (0, -0.302, 0.515), (0.75, 0.03, 0.09), mats["edge"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Seat_BackDarkWornLip", (0, 0.302, 0.515), (0.75, 0.03, 0.09), mats["edge"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Seat_LeftDarkWornLip", (-0.388, 0, 0.515), (0.03, 0.56, 0.088), mats["edge"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Seat_RightDarkWornLip", (0.388, 0, 0.515), (0.03, 0.56, 0.088), mats["edge"], bevel=0.012, collection_name="PROPS"))
    objects.extend(add_seat_grain(mats))

    # Legs and cross braces.
    for side_name, x in [("Left", -0.305), ("Right", 0.305)]:
        for row_name, y in [("Front", -0.23), ("Back", 0.235)]:
            objects.extend(add_leg(f"PROP_TavernChair_{row_name}{side_name}_ChunkyTaperedLeg", (x, y, 0.245), mats))

    add(cube("PROP_TavernChair_FrontCrossBrace", (0, -0.262, 0.295), (0.58, 0.045, 0.06), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_TavernChair_BackCrossBrace", (0, 0.265, 0.31), (0.58, 0.045, 0.06), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_TavernChair_LeftSideCrossBrace", (-0.332, 0.0, 0.285), (0.045, 0.47, 0.06), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_TavernChair_RightSideCrossBrace", (0.332, 0.0, 0.285), (0.045, 0.47, 0.06), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cylinder("PROP_TavernChair_FrontLowRoundStretcher", (0, -0.235, 0.175), 0.018, 0.56, mats["edge"], vertices=18, rotation=(0, math.radians(90), 0), bevel=0.004, collection_name="PROPS"))
    add(cylinder("PROP_TavernChair_BackLowRoundStretcher", (0, 0.235, 0.195), 0.018, 0.56, mats["edge"], vertices=18, rotation=(0, math.radians(90), 0), bevel=0.004, collection_name="PROPS"))

    # Back posts, broad plank backrest, crest rail, and carved details.
    add(cube("PROP_TavernChair_BackPost_LeftChunky", (-0.305, 0.295, 0.79), (0.078, 0.08, 0.66), mats["wood"], bevel=0.023, collection_name="PROPS"))
    add(cube("PROP_TavernChair_BackPost_RightChunky", (0.305, 0.295, 0.79), (0.078, 0.08, 0.66), mats["wood"], bevel=0.023, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Backrest_LowerBroadPlank", (0, 0.31, 0.77), (0.6, 0.07, 0.15), mats["wood"], bevel=0.024, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Backrest_UpperBroadPlank", (0, 0.31, 0.94), (0.64, 0.07, 0.17), mats["wood"], bevel=0.026, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Backrest_TopDarkWornCrest", (0, 0.305, 1.085), (0.73, 0.085, 0.075), mats["edge"], bevel=0.026, collection_name="PROPS"))
    add(cube("PROP_TavernChair_Backrest_MiddleDarkSeam", (0, 0.272, 0.855), (0.58, 0.026, 0.038), mats["edge"], bevel=0.007, collection_name="PROPS"))
    objects.extend(add_backrest_carving(mats))

    # Extra nicks and worn corners to keep the silhouette handcrafted.
    nick_points = [
        [(-0.35, -0.31, 0.59), (-0.31, -0.31, 0.592), (-0.27, -0.31, 0.589)],
        [(0.24, -0.31, 0.59), (0.29, -0.31, 0.586), (0.34, -0.31, 0.59)],
        [(-0.31, 0.268, 1.1), (-0.25, 0.266, 1.105), (-0.18, 0.268, 1.098)],
        [(0.15, 0.268, 1.101), (0.23, 0.266, 1.096), (0.31, 0.268, 1.103)],
    ]
    for index, points in enumerate(nick_points, start=1):
        add(
            bevel_curve(
                f"PROP_TavernChair_DarkHandcarvedNick_{index:02d}",
                points,
                mats["grain"],
                bevel_depth=0.005,
                bevel_resolution=1,
                resolution=6,
                collection_name="PROPS",
            )
        )

    add(cylinder("BASE_BakedSoftContactShadow", (0, 0.02, 0.004), 0.46, 0.008, mats["shadow"], vertices=64, scale=(1.05, 0.86, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.026, 0.03, 0.033)

    camera_data = bpy.data.cameras.new("CAM_TavernChair_Preview")
    camera = bpy.data.objects.new("CAM_TavernChair_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (1.42, -2.45, 1.22)
    camera.data.lens = 56
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 2.75
    camera.data.dof.aperture_fstop = 7.0
    look_at(camera, (0, 0.04, 0.62))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_TavernChairSoftbox", "AREA", (-2.1, -2.6, 2.7), 420, 3.2),
        ("LGT_Rim_TavernChairWarmEdge", "AREA", (1.9, 1.35, 1.95), 150, 1.8),
        ("LGT_Fill_TavernChairStudio", "POINT", (1.2, -1.5, 1.15), 58, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0.04, 0.62))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_TavernChair"
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


def render_preview(paths: dict[str, Path]) -> None:
    bpy.context.scene.render.filepath = str(paths["preview"])
    try:
        bpy.ops.render.render(write_still=True)
        return
    except Exception as first_error:
        print(f"Preview render failed with {bpy.context.scene.render.engine}: {first_error}", file=sys.stderr)

    try:
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        bpy.ops.render.render(write_still=True)
    except Exception as fallback_error:
        print(f"Preview render fallback failed: {fallback_error}", file=sys.stderr)


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
            "source": "Blender Python procedural generator",
        },
        "notes": [
            "Stylized fantasy tavern chair generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Warm brown wood, darker worn edges, chunky hand-hewn proportions, carved details, subtle geometric grain, and baked contact shadow.",
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
    build_tavern_chair(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    render_preview(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
