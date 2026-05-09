"""Generate a stylized medieval tavern table asset in Blender.

Run from Blender Python through the live MCP bridge when available, or through
background Blender via run_blender_asset.py. The script is repeatable: it
creates the source scene, exports a static GLB, renders a preview, and writes
metadata for the Artomata viewer.
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
    assign_mat,
    bevel_curve,
    bounds_for_objects,
    clear_scene,
    collection,
    cone,
    cube,
    cylinder,
    ensure_dir,
    link_to_collection,
    look_at,
    make_mat,
    scene_triangle_count,
    shade_smooth,
    write_json,
)

ASSET_SLUG = "tavern-wooden-table"
ASSET_NAME = "Tavern Wooden Table"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Furniture",
    "subject": "Round wooden tavern table",
    "visual_style": "Stylized medieval fantasy, chunky readable shapes, game-ready prop scale",
    "required_parts": [
        "round wooden tabletop",
        "four sturdy legs",
        "cross supports",
        "slight wear marks",
        "carved edge detail",
        "contact shadow",
    ],
    "material_palette": [
        "medium brown wood",
        "darker worn edges",
        "subtle scratches and dents",
        "soft translucent contact shadow",
    ],
    "rig_target": "none",
    "animation_clips": [],
    "viewer_framing": "3/4 top-down view, showing tabletop and legs clearly on a neutral background",
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
        "wood": make_mat("MAT_TavernTable_MediumWood", (0.45, 0.235, 0.105, 1), roughness=0.62),
        "edge": make_mat("MAT_TavernTable_DarkWornEdges", (0.22, 0.105, 0.045, 1), roughness=0.78),
        "scratch": make_mat("MAT_TavernTable_ScratchDent", (0.12, 0.065, 0.032, 1), roughness=0.88),
        "shadow": make_mat("MAT_TavernTable_Shadow", (0.018, 0.018, 0.02, 0.5), roughness=0.94, alpha=0.5),
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


def torus(
    name: str,
    loc: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
    *,
    vertices: int = 72,
    minor_segments: int = 8,
    collection_name: str = "PROPS",
) -> bpy.types.Object:
    run_operator(
        bpy.ops.mesh.primitive_torus_add,
        major_segments=vertices,
        minor_segments=minor_segments,
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=loc,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    assign_mat(obj, mat)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def add_rotated_cube(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    rotation_z: float,
    mat: bpy.types.Material,
    *,
    bevel: float = 0.004,
    collection_name: str = "PROPS",
) -> bpy.types.Object:
    obj = cube(name, loc, scale, mat, bevel=bevel, collection_name=collection_name)
    obj.rotation_euler[2] = rotation_z
    return obj


def add_tabletop_detail(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    top_z = 0.862

    for index, x in enumerate([-0.42, -0.21, 0.0, 0.21, 0.42], start=1):
        y_extent = math.sqrt(max(0.0, 0.62**2 - x**2))
        objects.append(
            bevel_curve(
                f"PROP_TavernTable_PlankSeam_{index:02d}",
                [(x, -y_extent, top_z), (x, y_extent, top_z)],
                mats["scratch"],
                bevel_depth=0.0045,
                bevel_resolution=1,
                resolution=4,
                collection_name="PROPS",
            )
        )

    scratch_paths = [
        [(-0.36, -0.08, top_z + 0.002), (-0.21, -0.05, top_z + 0.002), (-0.1, -0.09, top_z + 0.002)],
        [(0.18, 0.18, top_z + 0.002), (0.29, 0.2, top_z + 0.002), (0.39, 0.16, top_z + 0.002)],
        [(-0.08, 0.35, top_z + 0.002), (0.03, 0.31, top_z + 0.002), (0.12, 0.34, top_z + 0.002)],
        [(0.29, -0.31, top_z + 0.002), (0.36, -0.26, top_z + 0.002), (0.43, -0.28, top_z + 0.002)],
    ]
    for index, points in enumerate(scratch_paths, start=1):
        objects.append(
            bevel_curve(
                f"PROP_TavernTable_DarkScratch_{index:02d}",
                points,
                mats["scratch"],
                bevel_depth=0.006,
                bevel_resolution=1,
                resolution=8,
                collection_name="PROPS",
            )
        )

    dent_specs = [
        (-0.28, 0.19, 0.0, 0.023, (1.65, 0.72, 1)),
        (0.34, -0.04, 0.85, 0.018, (1.45, 0.75, 1)),
        (0.05, -0.38, -0.45, 0.017, (1.5, 0.68, 1)),
        (-0.49, -0.26, 0.35, 0.014, (1.35, 0.78, 1)),
    ]
    for index, (x, y, angle, radius, scale) in enumerate(dent_specs, start=1):
        objects.append(
            cylinder(
                f"PROP_TavernTable_DarkDent_{index:02d}",
                (x, y, top_z + 0.002),
                radius,
                0.005,
                mats["scratch"],
                vertices=18,
                rotation=(0, 0, angle),
                scale=scale,
                bevel=0.001,
                collection_name="PROPS",
            )
        )

    for index in range(18):
        angle = (math.tau / 18) * index
        radius = 0.725
        loc = (math.cos(angle) * radius, math.sin(angle) * radius, 0.79)
        objects.append(
            add_rotated_cube(
                f"PROP_TavernTable_CarvedEdgeMark_{index + 1:02d}",
                loc,
                (0.052, 0.011, 0.028),
                angle + math.pi / 2,
                mats["scratch"],
                bevel=0.002,
                collection_name="PROPS",
            )
        )

    return objects


def add_leg(
    name: str,
    loc: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
) -> list[bpy.types.Object]:
    leg = cone(
        name,
        loc,
        0.095,
        0.13,
        0.68,
        mats["wood"],
        vertices=22,
        collection_name="PROPS",
    )
    add_bevel(leg, 0.01, 2, apply=True)
    add_weighted_normals(leg)

    foot = cylinder(
        f"{name}_DarkWornFoot",
        (loc[0], loc[1], 0.018),
        0.12,
        0.036,
        mats["edge"],
        vertices=24,
        bevel=0.004,
        collection_name="PROPS",
    )
    return [leg, foot]


def build_table(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    add(cylinder("PROP_TavernTable_DarkOuterTabletopBand", (0, 0, 0.765), 0.72, 0.11, mats["edge"], vertices=72, bevel=0.018, collection_name="PROPS"))
    add(cylinder("PROP_TavernTable_RoundMediumWoodTabletop", (0, 0, 0.79), 0.68, 0.13, mats["wood"], vertices=72, bevel=0.026, collection_name="PROPS"))
    add(torus("PROP_TavernTable_TopCarvedDarkRim", (0, 0, 0.852), 0.69, 0.018, mats["edge"], vertices=72, minor_segments=8))
    add(torus("PROP_TavernTable_LowerDarkRim", (0, 0, 0.69), 0.68, 0.018, mats["edge"], vertices=72, minor_segments=8))

    add(torus("PROP_TavernTable_UndersideApronRing", (0, 0, 0.64), 0.47, 0.027, mats["wood"], vertices=64, minor_segments=8))
    add(cylinder("PROP_TavernTable_XCrossSupportBeam", (0, 0, 0.37), 0.045, 1.04, mats["wood"], vertices=20, rotation=(0, math.radians(90), 0), bevel=0.006, collection_name="PROPS"))
    add(cylinder("PROP_TavernTable_YCrossSupportBeam", (0, 0, 0.37), 0.045, 1.04, mats["wood"], vertices=20, rotation=(math.radians(90), 0, 0), bevel=0.006, collection_name="PROPS"))

    for index, angle in enumerate([math.radians(45), math.radians(135), math.radians(225), math.radians(315)], start=1):
        x = math.cos(angle) * 0.44
        y = math.sin(angle) * 0.44
        objects.extend(add_leg(f"PROP_TavernTable_ChunkyLeg_{index:02d}", (x, y, 0.34), mats))

    objects.extend(add_tabletop_detail(mats))
    add(cylinder("BASE_TavernTable_BakedSoftContactShadow", (0, 0, 0.004), 0.58, 0.008, mats["shadow"], vertices=72, scale=(1.18, 1.0, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.027, 0.029, 0.031)

    camera_data = bpy.data.cameras.new("CAM_TavernWoodenTable_Preview")
    camera = bpy.data.objects.new("CAM_TavernWoodenTable_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (1.85, -2.28, 1.34)
    camera.data.lens = 50
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 2.75
    camera.data.dof.aperture_fstop = 7.5
    look_at(camera, (0, 0.0, 0.52))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_TavernTable_KeySoftbox", "AREA", (-2.2, -2.7, 2.9), 440, 3.4),
        ("LGT_TavernTable_WarmRim", "AREA", (2.1, 1.35, 1.85), 135, 1.8),
        ("LGT_TavernTable_LowFill", "POINT", (1.2, -1.4, 1.15), 58, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0, 0.5))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_TavernWoodenTable"
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
            "source": "Blender procedural asset pipeline",
        },
        "notes": [
            "Stylized medieval fantasy tavern table generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Built from chunky round tabletop forms, four sturdy legs, cross supports, carved dark edge marks, and subtle scratch/dent wear.",
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
